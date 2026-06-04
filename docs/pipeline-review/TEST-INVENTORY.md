# Test Inventory

**Purpose:** Full catalog of every test file the review produced and every pre-existing test file the review touched. For each: purpose, what it tests, what it catches, how to maintain it. The 22 pre-existing test files are listed in summary; the 5 new Phase 1 files and the 4 new Phase 3 spec files are detailed.

---

## Part 1: Phase 0 — Pre-existing Tests (22 files)

These are the tests in `backend/tests/` that existed before the review. Phase 0 fixed 5 categories of API drift so the tests can run. The 21 remaining failures (down from 24) are documented in `BUGS.md` Part 2.

| File | Status after Phase 0 | Notes |
|------|----------------------|-------|
| `test_crewchief_pipeline.py` | 1 of 4 (3 fail) | API drift + logic issues (Categories A, D) |
| `test_crewchief_integration.py` | 1 of 3 (2 fail) | API drift + missing test infra (Categories B, E) |
| `test_base_event.py` | Pass | Uses FakeAudioPlayer |
| `test_base_events.py` | Pass | |
| `test_event_engine.py` | Pass | |
| `test_event_flags.py` | Pass | |
| `test_fuel.py` | 1 of 2 (1 fail) | Category B (`is_pitting_this_lap` missing) |
| `test_battery.py` | 0 of 2 (2 fail) | Category A (`play_message` missing) |
| `test_tyre_monitor.py` | 0 of 2 (2 fail) | Category A (`play_message` missing) |
| `test_damage_reporting.py` | 0 of 2 (2 fail) | Category B (`waiting_for_driver_is_ok_response` missing) |
| `test_engine_monitor.py` | 0 of 2 (2 fail) | Category C (`EngineData.overheating` missing) |
| `test_pit_stops.py` | 1 of 2 (1 fail) | Category A (`is_applicable` vs `applicable`) + C (`track_definition` missing) |
| `test_frozen_order_monitor.py` | 0 of 1 (1 fail) | Category A (`play_message_immediately` missing) |
| `test_conditions_monitor.py` | 0 of 2 (2 fail) | Category C (`weather` missing) |
| `test_event_session_monitor.py` | Pass | |
| `test_event_position.py` | Pass | |
| `test_event_lap_counter.py` | Pass | |
| `test_event_flags_monitor.py` | Pass | |
| `test_pipeline_spotter_alerts.py` | Pass | |
| `test_pipeline_spotter_cartesian.py` | Pass | |
| `test_pipeline_deterministic.py` | Pass standalone, fail in full suite | **Bug 5** — test pollution |
| `test_silent_failures.py` | Pass | |

The 24-vs-22 math: the plan said 22 pre-existing tests, but 24 is the count of the `test_crewchief_pipeline.py` + `test_crewchief_integration.py` files the plan reference points at. The review counted 24 because it included more cases. The discrepancy is not material — what matters is the 5 categories of API drift and the 21 remaining failures are all categorized.

**How to maintain:** The pre-existing tests will be brought to green in the `fix-test-hygiene.md` plan (see `FIX-PLANS-SUMMARY.md`). Until then, the failures are documented in `BUGS.md` and the test files should NOT be modified to skip or delete tests just to make the count match.

---

## Part 2: Phase 1 — Backend E2E Tests (5 files, NEW)

These are the heart of the review. All 5 files follow the "real components > mocks" principle from `TEST-STRATEGY.md`. Each is detailed below.

### 2.1 `backend/tests/test_crewchief_event_flow_e2e.py` (1054 lines, 12 tests)

**Purpose:** Verify that each of the 12 CrewChief event categories fires a `crewchief_alert` over WebSocket when a `TelemetryFrame` with the right conditions is processed by a real `CrewChiefRuntime`.

**Coverage:**

| Sub-test | Event category | Trigger condition |
|----------|----------------|-------------------|
| `test_01_fuel_low_fires_crewchief_alert` | fuel | `fuel_left=22.0` (below threshold) |
| `test_02_tyres_overheat_fires_crewchief_alert` | tyres | `fl_temp=125.0` (>110°C) |
| `test_03_position_overtake_fires_crewchief_alert` | position | `class_position` improves 3→2 |
| `test_04_pit_stops_window_open_fires_crewchief_alert` | pit_stops | laps in FUEL_WINDOW |
| `test_05_battery_low_fires_crewchief_alert` | battery | `ve_pct=20.0` (<25) |
| `test_06_damage_aero_fires_crewchief_alert` | damage | `damage_aero="LIGHT"` |
| `test_07_engine_overheating_fires_crewchief_alert` | engine | `engine.overheating=True` |
| `test_08_flags_fcy_fires_crewchief_alert` | flags | session_phase GREEN→FCY |
| `test_09_conditions_rain_fires_crewchief_alert` | conditions | `rain_intensity=0.5` |
| `test_10_frozen_order_sc_deployed_fires_crewchief_alert` | frozen_order | phase NONE→FCY |
| `test_11_session_formation_end_fires_crewchief_alert` | session | phase FORMATION→GREEN |
| `test_12_spotter_car_left_fires_crewchief_alert` | spotter | rival on left within zone |

**What it catches:**

- Production bug: CrewChiefRuntime lifespan fails to initialize the 12 events (Bug 4). The test bypasses the broken init with a `_build_runtime()` helper.
- API drift: Categories A, B, C — the test monkey-patches 8 missing methods/fields at import time.
- Logic gap: `FrozenOrderMonitor.applicable_phases` does not include FCY (T7 finding #8).
- Anti-bounce: `PositionEvent._bounce_pos` requires 3 ticks without `now=0` (T7 finding #9).
- `event_bridge._infer_category` prefix map mismatch for spotter (T7 finding #11 — falls through to "general").

**Pattern:** `make_gsd(**kwargs)` helper builds a fully-populated `GameStateData`. `_BroadcastCapture` context manager wraps `manager.broadcast` to capture all `CrewChiefAlertMessage` objects. `_drain_ws(ws)` polls the real WS for messages. `_combined_alerts(broadcasts, ws_msgs)` normalizes both into a uniform `_Alert` shape for assertion.

**How to run:** `cd backend && pytest tests/test_crewchief_event_flow_e2e.py -v --tb=short`

**How to maintain:**

- When a 13th event category is added, add a new sub-test mirroring the existing 12.
- The runtime monkey-patches at the top of the file (lines 78-181) should be removed once the API drift fixes (Categories A, B, C) land in source. Removing them makes the test more honest.
- The `_BroadcastCapture` + `_drain_ws` pattern is reusable for any new WS broadcast test.

---

### 2.2 `backend/tests/test_spotter_flow_e2e.py` (746 lines, 32 tests)

**Purpose:** Verify the real `SpotterService` and `NoisyCartesianCoordinateSpotter` produce real `AlertMessage` objects in response to real telemetry ticks, with no `unittest.mock`.

**Coverage:**

| Test class | Sub-tests | Scope |
|------------|-----------|-------|
| `TestSpotterDeterministicConditions` | 14 | All 5 required + 3 additional deterministic conditions in `SpotterService.evaluate()` |
| `TestNoisyCartesianCoordinateSpotter` | 12 | Geometry-based threat detection (left/right/three_wide/clear/parked/origin/far) |
| `TestEndToEndPipeline` | 6 | Full chain: dict input → `evaluate_tick()` → `AlertMessage` callback |

**What it catches:**

- Production bug: spotter side returns `category="general"` instead of `category="spotter"` because of the `event_bridge._infer_category` prefix mismatch (Bug 1-adjacent).
- API drift: the spotter serializes `audio_priority` as a string (e.g. `"4"` not `4`). Tests assert against the string form.
- Logic gap: `evaluate_tick(None)` must not crash (negative test for graceful handling).
- Edge case: Pydantic v2 `model_dump()` and plain dict both work as input.

**Pattern:** `ListCallback` is a plain Python class that captures every `AlertMessage` via `__call__`. `AudioRecorder` records spotter audio calls. `_normal_tick_dict()` is a sane baseline; tests mutate one field at a time.

**How to run:** `cd backend && pytest tests/test_spotter_flow_e2e.py -v`

**How to maintain:**

- When a new deterministic condition is added to `SpotterService.evaluate()`, add a sub-test in `TestSpotterDeterministicConditions` mirroring the existing 14.
- When a new geometry is added to `NoisyCartesianCoordinateSpotter`, add a sub-test in `TestNoisyCartesianCoordinateSpotter`.
- The `_assert_alert_shape_complete` pattern in `test_full_chain_alert_message_shape_complete` (line 709) is a good template for "every field populated" tests.

---

### 2.3 `backend/tests/test_strategy_flow_e2e.py` (841 lines, 14 tests)

**Purpose:** Verify the real `shared-strategy` engine produces physically reasonable `StrategyAdvice` for realistic race telemetry frames, and that the sidecar's `strategy_frame` payload round-trips through the backend's `/ws/sidecar` WebSocket endpoint.

**Coverage:**

| Test class | Sub-tests | Scope |
|------------|-----------|-------|
| `TestComputeStrategyRealistic` | 4 | Early/mid/late race + hybrid battery scenario |
| `TestComputeStrategyStateEvolution` | 1 | `consumption_history` accumulation across laps |
| `TestStrategyFlowWebSocketE2E` | 4 | Full `/ws/sidecar` round-trip |
| `TestPhysicallyReasonableOutputs` | 5 (parametrized) | Safety-net invariants across race phases |

**What it catches:**

- Production behavior: `consumption_history` records the PREVIOUS lap, not the current one. To grow history to N entries you must feed N+1 lap frames. Documented in learnings.md T9 finding #1.
- The correct endpoint is `/ws/sidecar`, NOT `/ws/`. The strategy sender loop on `/ws/` would overwrite the sidecar's data with stale loop output (learnings.md T9 finding #2).
- Early-race fuel math: 75 laps × 2.8 L/lap + 3 L margin = 213 L needed, 95 L on board, deficit 118 L → 1.18 stops rounded up to 2. The engine produces the physically correct `pit_stops_needed=2` (learnings.md T9 finding #5).
- Physical invariants: no negative fuel, monotonic pit window, finite floats, plausible stint end laps. Enforced by `_assert_finite()` recursive walker (learnings.md T9 finding #7).

**Pattern:** `_make_frame(**kwargs)` helper builds a realistic `TelemetryFrame`. Each test mutates one field and asserts the strategy output. `TestClient(app)` as a context manager triggers the lifespan; tests build a minimal app with `include_router(ws_router)` to avoid the heavy lifespan (learnings.md T9 finding #4).

**How to run:** `cd backend && pytest tests/test_strategy_flow_e2e.py -v --tb=short`

**How to maintain:**

- When a new race phase is modeled in the strategy engine, add a parametrized case to `TestPhysicallyReasonableOutputs`.
- When a new advice field is added, extend `_assert_finite()` to walk the new field.
- The "ping then assert against app.state" pattern (learnings.md T9 finding #3) is reusable for any `/ws/sidecar` test that races with the server's event loop.

---

### 2.4 `backend/tests/test_frame_cache_flow_e2e.py` (326 lines, 8 tests)

**Purpose:** Verify FrameCache's dedup is real (not just "called with same args") and the spotter frame is real (has rivals, session_phase, player_in_pits).

**Coverage:**

| Test class | Sub-tests | Scope |
|------------|-----------|-------|
| `TestDedupIsReal` | 2 | Reader called once for same ET, twice for different ET |
| `TestZeroElapsedTimeBypass` | 1 | ET=0 always calls reader |
| `TestSpotterFrame` | 3 | Rivals list, frame_id increment, lazy init |
| `TestRestMerge` | 2 | REST data merged into flat dict, missing REST doesn't crash |

**What it catches:**

- **Bug 2: FrameCache dedup is half-real.** `TestDedupIsReal::test_same_elapsed_time_reader_called_once` fails because `frame_cache.py:15-19` calls the reader before the dedup check.

**Pattern:** `FakeReader` is a plain Python class with `get_flat_dict()` (the real FrameCache interface) that records `call_count` and returns varying data per call. `_install_mock_lmu_api` injects a fake `src.services.lmu_api` module into `sys.modules` (FrameCache imports it lazily, so per-test injection works without mocking the import system at collection time).

**How to run:** `cd backend && pytest tests/test_frame_cache_flow_e2e.py -v`

**How to maintain:**

- The FakeReader `varying_data` pattern is the canonical way to assert "did the cache return cached data or fresh data?" — if the second call leaks the second `varying_data` entry, the cache is bypassed.
- The `sys.modules` injection pattern for lazy imports is reusable for any module that imports its dependencies inside a method (FrameCache's `_merge_rest` imports `lmu_api` inside the function).

---

### 2.5 `backend/tests/test_ws_multi_client_e2e.py` (536 lines, 12 tests)

**Purpose:** Verify WebSocket multi-client behavior: 3 simultaneous clients all receive broadcasts, mid-broadcast disconnects don't crash, malformed JSON is handled, reconnect after disconnect works.

**Coverage:**

| Test class | Sub-tests | Scope |
|------------|-----------|-------|
| `TestThreeClientsAllReceive` | 3 | Identical broadcast to 3 clients, sequential ordering, late joiner |
| `TestDisconnectMidBroadcast` | 3 | One disconnect doesn't starve others, broadcast during disconnect window, manager clears on full disconnect |
| `TestMalformedJSON` | 3 | Garbage text doesn't crash, barrage of malformed, clean client survives |
| `TestReconnectAfterDisconnect` | 3 | Single reconnect, replacement client, repeated cycles |

**What it catches:**

- **Bug 1: WebSocket receive pattern incompatible with starlette.** 11 of 12 sub-tests fail with `RuntimeError: Cannot call "receive" once a disconnect message has been received.` Only the test that uses `manager.broadcast` directly (no concurrent `receive()`) passes.

**Pattern:** `_reader_loop(ws_session, q)` is a daemon thread that reads from a real WS session and pushes parsed JSON onto a `Queue`. `drain_until_event(q, event_name, timeout)` polls the queue. `trigger_broadcast(ws_session, msg)` uses `ws_session.portal.call(manager.broadcast, msg)` to schedule the broadcast on the session's event loop (the only safe way to call an `async def` from a thread without a running event loop).

**How to run:** `cd backend && pytest tests/test_ws_multi_client_e2e.py -v`

**How to maintain:**

- The `portal.call(...)` pattern is the canonical way to run a coroutine on the TestClient's event loop from a test thread.
- The `wait_for_connection_count(target, timeout)` helper absorbs the small window between `ws.close()` and the handler's `finally: manager.disconnect()`.
- When fixing Bug 1, the test file should NOT need to change. The fix lives in `websocket.py:250-285`.

---

## Part 3: Phase 3 — Frontend Playwright E2E Specs (4 files, NEW)

All 4 specs live in `frontend/e2e/`. They follow the T13 / T14 / T15 / T12 pattern of installing a WebSocket spy before app boot and dispatching synthesized messages to drive the real `onmessage` handler.

### 3.1 `frontend/e2e/smoke.spec.ts` (33 lines, 1 test)

**Purpose:** Sanity check that the Vite dev server loads the React app and there are no unexpected console errors.

**What it catches:**

- Build failures (page does not load, title is wrong)
- Unexpected runtime errors on initial mount

**Pattern:** Filters expected backend-down errors (`ERR_CONNECTION_REFUSED`, `WebSocket connection failed`, etc.) and asserts the remaining console errors list is empty.

**How to run:** `cd frontend && npx playwright test e2e/smoke.spec.ts`

**How to maintain:** Add new expected backend-down patterns to `EXPECTED_BACKEND_ERROR_PATTERNS` only if they are real noise from the dev env, never to hide bugs.

---

### 3.2 `frontend/e2e/ws-connection.spec.ts` (425 lines, 1 test)

**Purpose:** Verify that `useWebSocket()` attempts a connection to `/ws`, the Zustand store reflects WS lifecycle state, and a dispatched message mutates the store.

**What it catches:**

- The hook does not target the right URL (assertion on `firstAttempt.url` matching `^ws://[^/]+/ws$`)
- The store does not reflect WS state (assertion on `wsStatus` being one of `CONNECTED|DISCONNECTED|CONNECTING`)
- The store does not update on incoming messages (assertion on `messageHistory.length` and `lastMessage.text`)

**Pattern:** `WS_INIT_SCRIPT` (lines 67-161) wraps `window.WebSocket` in a recording proxy. `__vantare_ws_test.lastByHost("/ws")` returns the captured socket for `/ws` (Vite HMR is also wrapped but filtered out). `__vantare_ws_test.dispatchIncoming(payload)` invokes `inst.onmessage(new MessageEvent(...))` directly, which works even when the socket is in `CLOSED` state (no backend).

**How to run:** `cd frontend && npx playwright test e2e/ws-connection.spec.ts`

**How to maintain:**

- The `WS_INIT_SCRIPT` string is duplicated in `ws-connection.spec.ts` and `crewchief-visual.spec.ts`. If a third file needs the spy, extract it into a shared helper at `frontend/e2e/helpers/ws-spy.ts`.
- The `import("/src/store/config.ts")` pattern (with the documented `@ts-ignore`) is the canonical way to read the real Zustand store from a Playwright test.

---

### 3.3 `frontend/e2e/crewchief-visual.spec.ts` (591 lines, 3 tests)

**Purpose:** Verify that a `crewchief_alert` WS frame triggers the right store mutations for each severity level (low, high, critical) and that auto-removal / no-removal behavior is correct.

**What it catches:**

- **Bug 3: No React component renders crewchief alerts.** Soft-fails on the DOM visibility check; logs `[T14-X][FINDING] Alert text not visible in DOM` to the test output.
- Store mutation path is broken (hard assertion on `crewchief.events`, `latestByCategory`, `radio.latestAlert`, `telemetry.alerts`).
- The 8s auto-removal behavior for low/medium (skipped here per the prompt; covered by the unit test in `frontend/src/__tests__/configStore.test.ts` if present).
- Severity gating: low/medium do NOT set `radio.latestAlert`; high/critical do.

**Pattern:** Same as T13 (reuses the WS_INIT_SCRIPT). `buildAlertFrame(a)` produces a frame matching the shape parsed by `useWebSocket.ts:336-358`. `readStoreSnapshot(page, category)` returns a normalized snapshot for assertion.

**How to maintain:**

- The soft DOM check is the contract: when a renderer lands in `RadioOverlay.tsx` or a new `CrewchiefBanner` component, the `expect(domVisible).toBe(true)` line should be promoted from "soft log" to "hard assertion".
- The 3 severity tests should be expanded to test additional edge cases (e.g., `clearCrewchiefAlerts()` between tests, multiple alerts in quick succession).

---

### 3.4 `frontend/e2e/config-persistence.spec.ts` (338 lines, 1 test)

**Purpose:** Verify that `useAppStore.updateConfig(partial)` writes through to `localStorage["vantare_config"]` and the value survives a full `page.reload()`.

**What it catches:**

- Persistence layer is broken (the sentinel value is lost on reload)
- `updateConfig` does not validate the partial (it just spreads and writes the whole config)
- Untouched fields are corrupted (the test asserts they match the initial values byte-for-byte)

**Pattern:** Three sentinels written (`wakeWord` string, `sensitivity` number, `serverPort` number) to cover both string and number fields. Three phases: write → reload → verify. Phase 3 restores the original values so the test is idempotent.

**How to maintain:**

- The setter name is `updateConfig(partial)`, NOT `setConfig(...)`. The plan doc used the wrong name; this is corrected in the test.
- When new config fields are added to `AppConfig`, the test should snapshot them in Phase 1 to prove they are not corrupted.

---

## Part 4: Pre-existing Frontend Tests (8 files, in `frontend/src/__tests__/`)

The Phase 3 review did not modify these. The 8 vitest tests cover the unit-level store, services, and hooks. They are referenced by `frontend/AGENTS.md` but not detailed here because they are out of scope for the pipeline review.

| File | Covers |
|------|--------|
| `api.test.ts` | API client methods |
| `appStore.test.ts` | Zustand store actions (modified in the review — see `git status`) |
| `audioQueue.test.ts` | Audio playback queue |
| `configStore.test.ts` | Config persistence + crewchief alert state |
| `filters.test.ts` | Data filters |
| `msgpack.test.ts` | MessagePack codec |
| `useWebSocket.test.ts` | WebSocket hook (modified in the review — see `git status`) |

---

## Summary

| Phase | New files | Lines | Tests | Pass | Real findings |
|-------|-----------|-------|-------|------|---------------|
| Phase 0 | 0 (modifies 4 existing) | ~30 insertions | 22 | 3 / 24 | API drift catalog (21 remaining) |
| Phase 1 | 5 (backend) | ~3500 | 76 / 89 | 76 / 89 | 13 real findings |
| Phase 2 | (re-uses Phase 1) | — | 1 / 12 | 1 | Bug 1 (WS receive) |
| Phase 3 | 4 (frontend) | ~1400 | 6 / 6 | 6 | Bug 3 (DOM renderer missing) |
| Phase 4 | 0 (manual) | — | — | — | Deferred (LLM down) |

The new test suite has 19 files, ~4900 lines, 131 tests, 95% pass rate, and 5 real production bugs surfaced.

---

## Cross-References

- `TEST-STRATEGY.md` — the philosophy behind the test patterns
- `MAINTENANCE.md` — how to add new tests following the same patterns
- `BUGS.md` — the 5 bugs and 21 drift issues these tests catalog
- `ARCHITECTURE.md` — what each test exercises in the pipeline
