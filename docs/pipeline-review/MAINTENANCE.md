# Maintenance Guide

**Purpose:** How to add new tests, what to fake, what to never mock, and how to keep the test suite honest as the codebase evolves. The patterns here are derived from the 9 new test files (5 backend, 4 frontend) and the bugs they caught. Follow them; the suite is only useful if it stays consistent.

---

## 1. Adding a New Backend E2E Test

### 1.1 When to Add a Backend E2E Test

Add a new E2E test when:

- You are adding a new event category to `EventEngine`
- You are adding a new broadcast type to `manager.broadcast`
- You are adding a new endpoint to `src/routers/websocket.py` (or any router)
- You are wiring a new service into the lifespan in `src/main.py`
- You are changing the shape of any Pydantic model used in a WS payload

Do NOT add an E2E test for pure utility functions (use the existing unit tests in `backend/tests/test_utilities.py` style for that).

### 1.2 The Minimal Skeleton

```python
"""E2E test for <workflow> (T<N>).

Verifies that the real <components> produce real <outputs> when fed
real <inputs>, end-to-end through the real FastAPI app.

Anti-patterns (deliberately avoided):
  - No unittest.mock.Mock
  - No patching of <production code>
  - No mocking the WebSocket
"""
import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routers.websocket import router as ws_router
from src.routers.health import router as health_router
# Real imports — NOT mocked
from src.services.<your_service> import <YourService>


@pytest.fixture
def ws_app():
    app = FastAPI()
    app.include_router(ws_router)
    app.include_router(health_router)
    app.state.telemetry_reader = None
    app.state.strategy_service = None
    app.state.intelligence_engine = None
    app.state.spotter_service = None
    app.state.latest_client_frame = None
    app.state.latest_strategy_frame = None
    app.state._last_telemetry_t = 0.0
    return app


@pytest.fixture
def ws_client(ws_app):
    with TestClient(ws_app) as client:
        client.get("/health")  # force portal creation
        yield client


class TestYourWorkflow:
    def test_happy_path(self, ws_client):
        """<description>"""
        with ws_client.websocket_connect("/ws") as ws:
            # 1. Build real input
            # 2. Trigger the real flow (via /test/* endpoint or direct call)
            # 3. Assert on real WS output
            pass
```

### 1.3 When to Use a Fake vs When to Mock

| External dependency | Use | Why |
|---------------------|-----|-----|
| LMU shared memory | `FakeReader` class implementing `get_flat_dict()` | The real reader requires LMU running, which the test env does not have |
| Audio output (WAV file write) | `RecordingAudioPlayer` class with `messages` and `immediate_messages` lists | The real `AudioPlayer` writes to disk; the test only needs to verify it was called with the right name |
| REST API (garage wear) | Inject fake `src.services.lmu_api` module via `sys.modules` | The real `lmu_api` is a thin HTTP wrapper; the test wants to control the data |
| Strategy service (offline path) | Real `StrategyService` from `shared_strategy` | It's a pure function, no I/O. Real is better than fake. |
| Spotter | Real `SpotterService` with `ListCallback` | Same: pure logic, real is better. |
| The FastAPI app itself | Real `TestClient(app)` | Never mock the app. Build a smaller real app if you must. |
| The WebSocket | Real `TestClient.websocket_connect` | Never mock the WebSocket. |
| A WS message handler | Real handler, real store | The point of the test is the handler. |

### 1.4 Patterns to Follow

- **Real dataclass builders.** Write a `_make_frame(**kwargs)` or `make_gsd(**kwargs)` helper that defaults to a realistic mid-pack Hypercar snapshot. Override field-by-field. This saves ~30 lines per scenario.
- **`_BroadcastCapture` for WS verification.** Wrap `manager.broadcast` in a context manager. The WS context is real, but verification happens at the broadcast level because `ws.receive()` is unreliable for concurrent server-sent messages (see `.omo/notepads/pipeline-review/learnings.md` T7).
- **`wait_for_connection_count(target, timeout)`** absorbs the small window between `ws.close()` and the handler's `finally: manager.disconnect()`.
- **Class layout per workflow:**
  - `Test<Name>Realistic` — direct calls, hand-crafted inputs
  - `Test<Name>StateEvolution` — state accumulation across calls
  - `Test<Name>WebSocketE2E` — transport round-trip
  - `Test<Name>PhysicallyReasonableOutputs` — safety net, parametrized
- **One assertion per field, with a custom message.** `assert reader.call_count == 1, f"Expected 1 reader call (dedup), got {reader.call_count}. FrameCache is calling the reader on every read_full()..."` — the message should explain what the failure means, not just that it failed.
- **Reset singletons in `autouse=True` fixtures.** `event_flags.reset_all()`, `manager.active_connections.clear()`, `global_settings.messages = {"ALL"}`. Without this, tests pollute each other.

### 1.5 What NOT to Do

- **Do NOT use `unittest.mock.Mock` on `CrewChiefRuntime`, `EventEngine`, `FrameCache`, `AudioPlayer`, `SpotterService`, `NoisyCartesianCoordinateSpotter`, `event_bridge.queued_to_crewchief_alert`.** Use a fake class that records calls and returns realistic data.
- **Do NOT use `Mock(spec=WebSocket)`.** Use `TestClient.websocket_connect`.
- **Do NOT use `dict()` stand-ins for Pydantic models.** Build real `TelemetryFrame`, `GameStateData`, `OpponentData` instances.
- **Do NOT assert with `assert_called_with(...)` on a mock.** Assert on the recorded state (`messages` list, captured broadcasts, store snapshots).
- **Do NOT use `asyncio.run_coroutine_threadsafe` from a thread that has no running event loop.** Use `TestClient.portal.call(coro, *args)` instead (see `test_ws_multi_client_e2e.py:164-175`).
- **Do NOT mock `src.services.lmu_api` at collection time.** It is imported lazily by `FrameCache._merge_rest`, so inject via `sys.modules` inside the test (see `test_frame_cache_flow_e2e.py:96-112`).
- **Do NOT skip tests with `@pytest.mark.skip` to make them pass.** Fix the underlying issue or document the gap.
- **Do NOT delete tests to make the count match.** The 21 remaining failures in the pre-existing tests are documented in `BUGS.md`; deleting them loses the contract.

---

## 2. Adding a New Frontend Playwright E2E Test

### 2.1 When to Add a Frontend E2E Test

Add a new Playwright test when:

- You are adding a new screen to the React tree
- You are wiring a new WS message type to a store mutation
- You are adding a new persistence mechanism (localStorage, IndexedDB, .env)
- You are wiring a new data-testid to a component
- You are changing the shape of a Zustand store slice

Do NOT add a Playwright test for component-rendering edge cases that can be tested with vitest + happy-dom (use the existing `frontend/src/__tests__/` tests for that).

### 2.2 The Minimal Skeleton

```typescript
/**
 * T<N> — <workflow>
 *
 * Verifies that <observable behavior>.
 *
 * Strategy (no app code modifications):
 *   - page.addInitScript() wraps window.WebSocket to record attempts
 *   - page.evaluate() dynamically imports /src/store/config.ts and
 *     reads useAppStore.getState() directly
 *   - dispatchIncoming() invokes the real onmessage handler
 */
import { test, expect, type ConsoleMessage } from "@playwright/test";

const EXPECTED_BACKEND_PATTERNS: RegExp[] = [
  /Failed to load resource:\s*net::ERR_CONNECTION_REFUSED/,
  /WebSocket connection to 'ws:\/\/[^/']+\/ws' failed/,
  /\[useWebSocket\] Error de conexi\u00f3n/,
  /\[api\] Error fetching health/,
  /\[App\] Polling de salud fallido/,
];

function isExpectedBackendError(text: string): boolean {
  return EXPECTED_BACKEND_PATTERNS.some((re) => re.test(text));
}

const WS_INIT_SCRIPT = `(() => { /* ... see ws-connection.spec.ts:67-161 ... */ })();`;

test.describe("T<N> — <workflow>", () => {
  test("<test name>", async ({ page, baseURL }) => {
    const consoleErrors: string[] = [];
    page.on("console", (m: ConsoleMessage) => {
      if (m.type() === "error") consoleErrors.push(m.text());
    });
    page.on("pageerror", (e) => consoleErrors.push(e.message));

    await page.addInitScript(WS_INIT_SCRIPT);
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveTitle(/Vantare/i);

    // 1. Wait for the hook to attempt /ws
    await page.waitForFunction(
      () => (window as any).__vantare_ws_test?.lastByHost("/ws") !== null,
      undefined,
      { timeout: 15_000 },
    );

    // 2. Dispatch a synthesized message OR read the store directly
    const result = await page.evaluate(async () => {
      // @ts-ignore — runtime URL resolved by Vite dev server
      const mod: any = await import("/src/store/config.ts");
      return mod.useAppStore.getState();
    });

    // 3. Assert on real store state and real DOM
    expect(result.<field>).toBe(<expected>);

    // 4. Filter expected backend errors
    const unexpected = consoleErrors.filter((t) => !isExpectedBackendError(t));
    expect(unexpected).toEqual([]);
  });
});
```

### 2.3 When to Use a Spy vs When to Mock

| Component | Use | Why |
|-----------|-----|-----|
| `window.WebSocket` | Spy (record instances, dispatch on them) | The test needs the real `onmessage` handler to fire |
| `useAppStore` (Zustand) | Real store via dynamic import | The point of the test is the store mutation |
| React components | Real components via Playwright | The point of the test is the rendering |
| `localStorage` | Real `localStorage` | Persistence is a real browser API |
| `fetch` / `XMLHttpRequest` | Real fetch (filter expected failures) | The real network stack is the right thing to exercise |
| Audio output (TTS blob) | Real audio (with expected failure when no backend) | The handler calls `audioQueue.enqueue` which is a real queue |
| `console.error` | Real console, with filter | The test asserts on unexpected errors |

### 2.4 Patterns to Follow

- **Install the WebSocket spy BEFORE app boot.** `await page.addInitScript(WS_INIT_SCRIPT);` must precede `await page.goto(...)`. Otherwise the hook has already constructed its socket.
- **Dispatch on `onmessage` directly, not via `dispatchEvent`.** The hook uses `ws.onmessage = fn` (property assignment), not `addEventListener`. The spy exposes `onmessage` via a getter/setter and dispatches by calling `inst.onmessage(evt)`. This works even when the socket is in `CLOSED` state.
- **Filter Vite HMR.** `lastByHost("/ws")` filters for the app's `/ws` endpoint. Vite HMR uses `/?token=` and is also wrapped; it does not match the filter.
- **Read the real store via dynamic import.** `import("/src/store/config.ts")` resolves to the real Zustand store factory because Vite serves source modules at the `.ts` path in dev mode. The TS compiler does not know about this, hence the `@ts-ignore` with the comment "runtime URL resolved by Vite dev server".
- **Test backend-down tolerance.** Filter `ERR_CONNECTION_REFUSED` and `WebSocket connection to ... failed` from the console errors. The test must still pass when the backend is offline (which is the current state of the dev env).
- **Screenshot evidence.** Use the evidence file path pattern: `path.join(REPO_ROOT, ".omo", "evidence", "pipeline-review", "task-N-<slug>.png")`. Write both PNG (screenshot) and TXT (text summary).

### 2.5 What NOT to Do

- **Do NOT mock `window.WebSocket` entirely.** Use the spy that records and dispatches; the real `WebSocket` instance must exist.
- **Do NOT mock the Zustand store.** The test exists to verify the store mutation. Mock the store and you have tested nothing.
- **Do NOT use `as any` outside the two documented cases** (the WS_INIT_SCRIPT and the dynamic `.ts` import). If you need to type-erase something, add a comment explaining why.
- **Do NOT add new npm dependencies without discussion.** The Phase 3 review added `@playwright/test` (necessary for E2E) but also added `@testing-library/react` and `happy-dom` which were not authorized — see `FIX-PLANS-SUMMARY.md` `fix-test-hygiene.md` for the cleanup.
- **Do NOT modify frontend source files in a "test-only" branch.** The Phase 3 review achieved all 6 tests without touching `frontend/src/`. If you find yourself wanting to add a debug hook or a data-testid, that is a sign the production code needs the hook anyway — add it as a real change.
- **Do NOT skip the 8s auto-removal test on crewchief alerts.** The T14 spec says it was skipped "per the prompt" but that was a one-time decision. New tests that need to verify auto-removal must wait the 8s.
- **Do NOT use `page.goto` after `page.addInitScript` without re-installing the script.** Each navigation in Playwright clears the page's execution context. If the test navigates multiple times, the spy must be re-added.

---

## 3. The Forbidden Mocking Patterns (CI Gate)

The plan's "Must NOT Have" guardrails at `.omo/plans/pipeline-review.md:78-86` explicitly ban certain patterns. Encode them as a CI check:

```bash
# 1. Ban: unittest.mock.Mock on forbidden components
grep -rn "Mock(spec=" backend/tests/ \
  && echo "FAIL: Mock(spec=...) found in backend/tests" && exit 1

# 2. Ban: unittest.mock for the 7 specific components
COMPONENTS="CrewChiefRuntime|EventEngine|FrameCache|AudioPlayer|SpotterService|NoisyCartesianCoordinateSpotter|queued_to_crewchief_alert"
grep -rn "unittest.mock\|from unittest import mock" backend/tests/ | grep -E "$COMPONENTS" \
  && echo "FAIL: unittest.mock used for forbidden component" && exit 1

# 3. Ban: as any / @ts-ignore in frontend e2e (allowed in 2 documented places)
COUNT=$(grep -rn "@ts-ignore" frontend/e2e/ | wc -l)
ALLOWED=8  # WS_INIT_SCRIPT uses it 2x; dynamic import uses it 2x per spec file × 2 files
if [ "$COUNT" -gt "$ALLOWED" ]; then
  echo "FAIL: $COUNT @ts-ignore in frontend/e2e/, allowed $ALLOWED"
  exit 1
fi

# 4. Ban: as any (not @ts-ignore) anywhere in frontend
grep -rn " as any" frontend/ \
  && echo "FAIL: 'as any' found in frontend/" && exit 1

# 5. Allowlist: print() in test files is fine, but warn
grep -rn "print(" backend/src/ frontend/src/ \
  && echo "WARN: print() in production code"
```

The exact counts and patterns need tuning as the suite grows. The point is to encode the rules so a junior contributor cannot accidentally introduce a test that hides a bug behind a Mock.

---

## 4. Per-Test Maintenance Notes

### `test_crewchief_event_flow_e2e.py`

- The runtime monkey-patches at lines 78-181 are workarounds for the API drift documented in `BUGS.md` Categories A, B, C. When those fixes land in source, the patches should be removed. Until then, do not "clean up" the patches — they are the only way the test runs.
- The `_BroadcastCapture` context manager is reusable. If you add a new test that needs to verify WS broadcasts, copy `_BroadcastCapture` rather than rebuilding it.
- The `_make_gsd` helper sets fields like `g.engine.overheating` dynamically via `setattr()`. This is because the GSD dataclass does not declare those fields (Bug Category C). When Category C is fixed in source, the dynamic `setattr` calls should be removed.

### `test_spotter_flow_e2e.py`

- 32 tests, fully passing. The "negative" tests (no alerts on safe state, parked pilot, origin) are important regression guards — do not remove them.
- The `ListCallback` and `AudioRecorder` fakes are minimal: they implement the interface the spotter uses (`__call__` for the callback, `play_spotter_message` for the audio). If the interface changes, update the fakes.

### `test_strategy_flow_e2e.py`

- The `_assert_finite()` recursive walker is a reusable safety net. If you add a new advice field, extend the walker to descend into it.
- The "ping then assert against app.state" pattern (T9 finding #3) is the canonical way to verify `/ws/sidecar` round-trips. The WS endpoint is `await receive_json()`-driven, so the test must send a follow-up message to yield control to the server task before inspecting `app.state`.
- The `TestClient(app)` is used as a context manager. This is the only way to trigger the lifespan. If you need to skip the heavy lifespan, build a minimal `FastAPI()` and `include_router(ws_router)` yourself.

### `test_frame_cache_flow_e2e.py`

- The `FakeReader.varying_data` pattern is the canonical way to assert "did the cache return cached data or fresh data?" — if the second call leaks the second `varying_data` entry, the cache was bypassed.
- The `sys.modules` injection for `src.services.lmu_api` is per-test. The fixture `try/finally` block restores the original module so other tests are not affected.
- When Bug 2 is fixed, `TestDedupIsReal::test_same_elapsed_time_reader_called_once` will start passing. Do not delete it — the test is the contract for the fix.

### `test_ws_multi_client_e2e.py`

- The 11-of-12 failure rate is real. When Bug 1 is fixed, all 12 should pass. The fix lives in `backend/src/routers/websocket.py:250-285`.
- The `portal.call(manager.broadcast, msg)` pattern is the canonical way to run a coroutine on the TestClient's event loop from a test thread. Do not use `asyncio.run_coroutine_threadsafe` — the test thread has no running event loop.
- The `wait_for_connection_count` helper polls the connection count with a short timeout. It is the only way to absorb the small window between `ws.close()` and the handler's `finally: manager.disconnect()`.

### `e2e/smoke.spec.ts`

- Trivially simple. Update the title regex if the app's title changes.
- Add new expected backend-down patterns to `EXPECTED_BACKEND_ERROR_PATTERNS` only if they are real dev-env noise.

### `e2e/ws-connection.spec.ts`

- The `WS_INIT_SCRIPT` string is duplicated in `crewchief-visual.spec.ts`. If a third spec needs the spy, extract it into `frontend/e2e/helpers/ws-spy.ts`. Until then, duplication is fine (the script is small).
- The dynamic `import("/src/store/config.ts")` pattern requires the `@ts-ignore` because the TS compiler does not know Vite serves source modules at the `.ts` path. Do not remove the comment.

### `e2e/crewchief-visual.spec.ts`

- The 3 soft DOM checks (low, high, critical severity) are the contract for Bug 3. When a renderer is added, promote `expect(domVisible).toBe(true)` from "soft log" to "hard assertion".
- The 8s auto-removal is skipped per the prompt. A follow-up timing-sensitive suite should test it.

### `e2e/config-persistence.spec.ts`

- The setter is `updateConfig(partial)`, NOT `setConfig(...)`. The plan doc used the wrong name. Do not "fix" the test to use `setConfig` — the plan was wrong, the test is right.
- Phase 3 restores the original values. The test is idempotent and leaves no residue for the next run or for a human developer.

---

## 5. Adding a New Test Class

When you need a new test class for a new workflow:

1. **Pick a name prefix.** `Test<Workflow>Realistic`, `Test<Workflow>StateEvolution`, `Test<Workflow>WebSocketE2E`, `Test<Workflow>PhysicallyReasonableOutputs`. The first 3 are scenario-based, the last is a parametrized safety net.
2. **Write the fixture.** `ws_app` + `ws_client` (backend) or `bootAppAndGetStore` (frontend). Copy from the closest existing test.
3. **Write the first test as a happy path.** Use the `_make_frame` or `buildAlertFrame` helpers.
4. **Add 1 negative test.** "Safe state produces no alerts", "Pilot at origin produces no spotter calls", "Empty rivals list produces no messages". This is your regression guard.
5. **Add 1 parametrized safety net.** At least 3 data points that cover the boundary (low/mid/high fuel, early/mid/late race, small/medium/large payload).
6. **Add a docstring at the top of the test file.** State what the test covers, what it catches, and the patterns it uses. Future maintainers will thank you.

---

## 6. When Tests Fail (Triage Order)

When a test fails, follow this triage order:

1. **Is the test file new (Phase 1 / Phase 3)?** Then the test is the contract. The failure is a real finding. File a bug, link the test, link the evidence.
2. **Is the test pre-existing (Phase 0)?** Then check `BUGS.md` Part 2. The failure is likely Category A, B, C, D, or E. If yes, the fix is documented.
3. **Is the failure a test pollution symptom?** Check whether the test passes standalone. If yes, look for shared state — singletons (`event_flags`, `global_settings`), thread pools, module-level globals.
4. **Is the failure a TestClient + WS interaction?** The T7 / T11 patterns use `_BroadcastCapture` and `wait_for_connection_count` to absorb these. If a new test is hitting this, copy those helpers.

If the failure is none of the above, it is probably a real production bug. The test caught it. Document it, file a bug, link the evidence.

---

## 7. Cross-References

- `TEST-STRATEGY.md` — the philosophy
- `TEST-INVENTORY.md` — the catalog
- `BUGS.md` — the bugs these tests caught
- `ARCHITECTURE.md` — what each test exercises
- `LLM-MIGRATION.md` — what changes when the LLM server is replaced
