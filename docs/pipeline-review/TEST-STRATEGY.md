# Test Strategy

**Purpose:** Document the testing philosophy the review adopted. The headline principle is "real components > mocks" but with sharp, documented exceptions. Every test in the new E2E suite follows these rules. Every future test should follow them too.

---

## The Core Principle: Real Components Over Mocks

A test should exercise the real code path it claims to cover. If the test uses `unittest.mock.Mock` to replace the unit under test, the test is asserting that the mock was called with the right arguments, not that the real code does the right thing. That is why the old test suite — full of `mock_event.play_message.assert_called_with(...)` — passed while the production system was broken.

The new E2E tests follow three rules:

1. **Real WebSocket.** Every backend WS test uses `fastapi.testclient.TestClient` with `client.websocket_connect('/ws')` against a real `app` and the real `ws_router`. No `Mock(spec=WebSocket)`. No monkey-patched `send`.
2. **Real dataclasses.** Every telemetry test builds a real `TelemetryFrame` (for strategy) or a real `GameStateData` (for crewchief). No `dict()` stand-ins. The test asserts on Pydantic `.model_dump()` output, not on hand-built dicts.
3. **Real assertions.** A test asserts that the WebSocket received a `CrewChiefAlertMessage` with `category == "fuel"` and `subtype == "fuel_low"`, not that `mock_event.play_message` was called. A test asserts that `ap.messages` (a recording audio player, see below) is non-empty, not that the queue mock returned the right thing.

The exceptions are sharp and documented below.

---

## When Mocks Are Acceptable (and When They Are Not)

### Forbidden: `unittest.mock.Mock` on Internal Components

The review's "must not do" list explicitly bans `unittest.mock.Mock` for:

- `CrewChiefRuntime`
- `EventEngine`
- `FrameCache`
- `AudioPlayer`
- `SpotterService`
- `NoisyCartesianCoordinateSpotter`
- `event_bridge.queued_to_crewchief_alert`

If a test mocks any of these, it is not testing the pipeline. It is testing that the mock received the right call. That is a test of the test's assumptions, not of the code.

The F2 verification report (`APPROVED w/ documented violations` at `.omo/plans/pipeline-review.md:1098`) confirmed this rule held across the new tests.

### Acceptable: Fakes That Implement the Real Interface

A "fake" is a plain Python class that implements the same interface as the real component, records calls, and returns realistic data. Fakes are encouraged when the real component depends on an external impossibility (LMU shared memory, GPU, microphone, a real HTTP service). The new tests use these fakes:

| Fake | Real component it replaces | Where it lives |
|------|----------------------------|----------------|
| `FakeReader` | `LMUReader` (reads from LMU shared memory) | `backend/tests/test_frame_cache_flow_e2e.py:30-65` |
| `RecordingAudioPlayer` | `AudioPlayer` (would play WAV files) | `backend/tests/test_crewchief_event_flow_e2e.py:195-296` |
| `ListCallback` | A `broadcast_callback` (would push to WS) | `backend/tests/test_spotter_flow_e2e.py:54-69` |
| `AudioRecorder` | `AudioPlayer` for spotter | `backend/tests/test_spotter_flow_e2e.py:72-90` |
| `FakeAudioPlayer` | `AudioPlayer` for pre-existing tests | `backend/src/intelligence/base_event.py:111` (test fixture) |
| `module: src.services.lmu_api` | The lazy-imported `lmu_api` module | injected via `sys.modules` in `test_frame_cache_flow_e2e.py:96-112` |

The pattern is: the fake has the same method names and signatures as the real thing. The test asserts on the data the fake returned (call count, call args, recorded messages), not on the fake's "mocking" behavior.

### Acceptable: Real External HTTP/WebSocket Wrappers

`TestClient` from `fastapi.testclient` is real: it runs the app in a separate thread with a real ASGI interface. `httpx.AsyncClient` is real. The frontend `WebSocket` wrapper in `ws-connection.spec.ts` is a real browser-side WebSocket that the test dispatches `MessageEvent`s on (via `__vantare_ws_test`).

What is forbidden: mocking `WebSocket` itself, mocking `httpx.AsyncClient`, or replacing the `app` object with a fake.

### Acceptable: Skipping Heavy Lifespan

The full `app` lifespan in `src/main.py` instantiates `EventStore`, `SpotterService`, `IntelligenceEngine`, `CrewChiefV4`, TTS services, and more. None of these are needed for a focused WS test. The new tests build a minimal `FastAPI()` and `include_router(ws_router)` themselves (see `test_ws_multi_client_e2e.py:33-50` and `test_strategy_flow_e2e.py`'s pattern in the learnings file). This is **not mocking** — it is composing a smaller real app. The router, the `manager`, the `WebSocket` machinery, and the `await manager.broadcast` flow are all real.

### Acceptable: Filtering Expected Console Errors

The frontend tests run with the backend down (the LLM server is offline, so the FastAPI server cannot fully start). The test sees `Failed to load resource: net::ERR_CONNECTION_REFUSED` and similar. The tests filter these expected errors with regex patterns (see `ws-connection.spec.ts:40-46`) and assert on the *unexpected* errors. This is not a workaround for a bug; it is honest reporting of "the test environment is degraded, here is what we filter and why".

---

## The "Real WS, Real Dataclasses, Real Assertions" Principle

Every Phase 1 backend E2E test follows the same shape:

1. **Build a real app with real routers.** No `app = Mock()`.
2. **Build real components.** `CrewChiefRuntime`, `SpotterService`, `StrategyService`, `FrameCache`. No `Mock(spec=...)`.
3. **Inject a fake only at the external boundary.** For the LMU reader, use `FakeReader`. For the audio output, use `RecordingAudioPlayer`. The fakes record calls and return data, they do not impersonate the system under test.
4. **Run the real code path.** Call `process_tick(frame)`, `evaluate_tick(tick)`, `compute_strategy(frame)`, `read_full()`. These are the production entry points.
5. **Assert on the real output.** The WS broadcast contents, the `AudioPlayer.messages` list, the `StrategyAdvice` fields, the `frame_id` count, the `AlertMessage` payload. No `assert_called_with`.

The frontend Phase 3 tests follow the analogous shape for the React side:

1. **Boot the real Vite app.** Playwright loads the dev server on `http://localhost:1420`.
2. **Capture real WebSocket instances.** `page.addInitScript()` wraps `window.WebSocket` so the test can record every socket the app opens.
3. **Dispatch on the real onmessage handler.** `__vantare_ws_test.dispatchIncoming(payload)` invokes `inst.onmessage(evt)`, which is the same property assignment `useWebSocket.ts:131` does. The real store mutation path runs.
4. **Read the real store via dynamic import.** `import("/src/store/config.ts")` resolves to the real Zustand store factory because Vite serves source modules at the `.ts` path in dev.
5. **Assert on the real store state and the real DOM.** `useAppStore.getState().crewchief.events.length`, `page.getByText(alert).isVisible()`. No mock store, no fake components.

---

## Concrete Examples

### Good: Real WS + Recording Audio Player

From `backend/tests/test_crewchief_event_flow_e2e.py:724-750`:

```python
def test_01_fuel_low_fires_crewchief_alert(self, ws_client_with_ap):
    """fuel/low_fuel_warning flows through to WS."""
    ws_client, ap = ws_client_with_ap
    gsds = [
        dict(completed_laps=2, fuel_left=50.0, now=100.0),
        dict(completed_laps=3, fuel_left=45.0, now=101.0),
        dict(completed_laps=4, fuel_left=40.0, now=102.0),
        dict(completed_laps=5, fuel_left=22.0, now=103.0),
    ]
    with _BroadcastCapture() as cap:
        with ws_client.websocket_connect('/ws') as ws:
            resp = ws_client.post("/test/tick", json={"gsds": gsds})
            assert resp.status_code == 200, resp.text
            time.sleep(0.1)
            msgs = _drain_ws(ws, max_messages=8, timeout_s=1.5)
    alerts = _combined_alerts(cap.captured, msgs)

    fuel_alerts = [a for a in alerts if a.category == "fuel"]
    assert fuel_alerts, f"No fuel alert. Categories: {[a.category for a in alerts]}"
    alert = fuel_alerts[0]
    assert alert.event == "crewchief_alert"
    assert alert.subtype == "fuel/low_fuel_warning"
    assert alert.severity in ("low", "medium", "high", "critical")

    fuel_msgs = [m for m in ap.messages if m.name == "fuel/low_fuel_warning"]
    assert fuel_msgs, f"audio_player.messages missing fuel/low_fuel_warning. Got: {[m.name for m in ap.messages]}"
```

The test opens a real WS, runs the real `/test/tick` endpoint, captures real `manager.broadcast` calls, drains real WS messages, and asserts on the real `RecordingAudioPlayer.messages` list. The `ap` (recording audio player) is a `RecordingAudioPlayer` instance — a plain Python class, not a Mock.

### Good: Real Strategy Engine + Real WS Sidecar

From `backend/tests/test_strategy_flow_e2e.py` (and the T9 verdict in `.omo/notepads/pipeline-review/learnings.md`):

```python
# Real imports — NOT mocked
from shared_strategy import (
    StrategyAdvice, StrategyState, TelemetryFrame, TrackConfig,
    compute_strategy,
)
from shared_strategy.models import CompetitorTelemetry
from src.routers.websocket import router as ws_router
```

The test calls the real `compute_strategy(frame)` and gets back a real `StrategyAdvice`. Then it connects a real `TestClient` to the real `ws_router`'s `/ws/sidecar` endpoint and pushes a real `strategy_frame` payload (same shape as `sidecar/main.py:99-107` produces in production). The backend stores it in `app.state.latest_strategy_frame` exactly as the production path does.

### Bad: What the Old Tests Did

```python
# OLD test_crewchief_pipeline.py style — this is what the review replaced
def test_fuel_low_fires_crewchief_alert():
    mock_ap = Mock()
    engine = EventEngine(audio_player=mock_ap)
    engine.process_tick(make_fuel_low_frame())
    mock_ap.play_message.assert_called_with("fuel/low_fuel_warning")
    # ^^ This test passes even if EventEngine.process_tick is a no-op,
    #    as long as it calls play_message. It does not test that the
    #    audio player actually receives the message, or that the message
    #    reaches the WS, or that the frontend reacts. The Mock hides
    #    every layer below it.
```

### Acceptable Boundary: Workarounds in the Test File

The T7 test file has 8 distinct runtime workarounds at import time (see `.omo/notepads/pipeline-review/learnings.md` T7 section). These are NOT mocks — they are real monkey-patches that add the missing methods (`play_message`, `play_message_immediately`, `is_applicable`, missing flag fields, `ap=` kwarg on 9 event classes). The point is: the test file makes the production code work, then exercises the real pipeline. The workarounds are documented in the file's docstring and they exist to surface the API drift as a finding (Categories A, B, C in `BUGS.md`), not to hide it.

The cleanest long-term fix is to lift these workarounds into the source files (see `BUGS.md` Categories A through C). Once that is done, the T7 test file drops the runtime patches and just runs the real code.

---

## What About the Frontend?

The frontend Phase 3 tests follow the same principle with a different shape. The "real component" on the frontend is the React tree plus the Zustand store. The "fake" is the captured `WebSocket` instance whose `onmessage` the test invokes directly (because the real backend is down).

The justification: the LLM server is offline, so the FastAPI backend cannot fully start. The frontend boots fine, the Vite dev server serves the real React tree, the real `useWebSocket` hook is loaded, and the real `useAppStore` Zustand store is instantiated. The test cannot open a real WS to a real backend, so it synthesizes a message on the captured socket instead. This drives the real `onmessage` handler, which calls the real `pushCrewchiefAlert` action, which mutates the real store. The DOM rendering is the only soft check (see `BUGS.md` Bug 3 — no renderer yet).

When the LLM server is back and the backend can run end-to-end, the T13 test can be expanded to do a real round-trip: open a real WS, broadcast a real `crewchief_alert` from a `test` endpoint, and assert on the visible DOM. Until then, the synthesized-message path is the strongest signal available.

---

## Anti-Patterns to Avoid in Future Tests

These are explicit "do not" items, lifted from the plan's `.omo/plans/pipeline-review.md:78-86` "Must NOT Have" guardrails:

- **No `unittest.mock.Mock` for `CrewChiefRuntime`, `EventEngine`, `FrameCache`, `AudioPlayer`, `SpotterService`, `NoisyCartesianCoordinateSpotter`.** Use a fake that records calls and returns realistic data.
- **No `mock.Mock(spec=WebSocket)`.** Use `TestClient.websocket_connect` for backend tests. For frontend, capture real WS instances with `page.addInitScript()`.
- **No `dict()` stand-ins for Pydantic models.** Build real `TelemetryFrame`, `GameStateData`, `OpponentData` instances.
- **No `assert_called_with(...)` style assertions.** Assert on the recorded state (`messages` list, captured broadcasts, store snapshots).
- **No `print()` in production code.** Use the `logging` module.
- **No `allow_origins=["*"]` CORS.** Use `settings.FRONTEND_ORIGIN`.
- **No `as any` / `@ts-ignore` in TypeScript** (except the documented 2-line case in T13/T14 where the test dynamically imports a `.ts` path that the TS compiler does not know about — see `MAINTENANCE.md`).
- **No adding npm dependencies without discussion.** The Phase 3 review added `@playwright/test` (necessary for E2E) and `@testing-library/react` + `happy-dom` (unauthorized, see `FIX-PLANS-SUMMARY.md`).
- **No modifying event business logic in `backend/src/intelligence/events/`.** Tests exercise the events; they do not change the events. The exception is the T7 runtime patches which are test-file-only, not source changes.
- **No touching the LMU shared-memory C extension internals.** Tests inject data at the Python boundary (`FakeReader`), not the C level.

---

## CI Gate Suggestions

To enforce these rules in CI, add the following greps to the pre-commit or pipeline check:

```bash
# Ban: unittest.mock.Mock for the forbidden components
grep -rn "Mock(spec=" backend/tests/                  # should be empty
grep -rn "unittest.mock" backend/tests/ | \
  grep -E "CrewChiefRuntime|EventEngine|FrameCache|AudioPlayer|SpotterService|NoisyCartesianCoordinateSpotter"  # should be empty

# Ban: bare @ts-ignore in frontend e2e (allowed in 2 documented places)
grep -rn "@ts-ignore" frontend/e2e/  # should show only the WS_INIT_SCRIPT + import("*.ts") lines

# Ban: npm dep changes without a note
git diff frontend/package.json  # review manually
```

These are suggestions, not implemented CI. See `MAINTENANCE.md` for the full maintenance plan.

---

## Cross-References

- `TEST-INVENTORY.md` — every test file, what it covers, how to maintain it
- `MAINTENANCE.md` — how to add a new E2E test following these principles
- `BUGS.md` — the bugs these tests caught
- `ARCHITECTURE.md` — what the pipeline looks like, for context on what each test is exercising
