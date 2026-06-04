# Bugs and API Drift

**Purpose:** Catalog every bug and contract drift issue the test review surfaced. The 5 real production bugs are listed first with severity, file path, line numbers, root cause, and the test that catches them. The 21 API drift issues follow, categorized A through E, with the fix that would resolve each.

---

## Part 1: Real Production Bugs (5)

These are the bugs the new E2E tests caught. None of them were visible from the old mock-heavy unit tests. Each is a real defect in the production code path: the system behaves incorrectly in production, not just in tests.

---

### Bug 1 — WebSocket Receive Pattern Incompatible With Starlette (HIGH)

**File:** `backend/src/routers/websocket.py:250-285`

**Root cause:** The `websocket_endpoint` handler uses a single `await websocket.receive()` call inside its main loop, then unpacks the result and branches on `raw.get("type") == "websocket.receive"`. With TestClient, after a disconnect sentinel is consumed, subsequent `receive()` calls raise `RuntimeError: Cannot call "receive" once a disconnect message has been received.`. The same pattern is fragile in production if a client sends a malformed frame after a partial disconnect: the loop re-enters `receive()` and the connection state machine in starlette rejects the call.

The 11-of-12 failure rate in `test_ws_multi_client_e2e.py` proves the pattern is not stable. Only the test that uses `manager.broadcast` directly (with no concurrent `receive()`) passes. Every other test (3 simultaneous clients, mid-broadcast disconnect, malformed JSON, reconnect) hits the pattern failure.

**Test that catches it:** `backend/tests/test_ws_multi_client_e2e.py` — `TestThreeClientsAllReceive`, `TestDisconnectMidBroadcast`, `TestMalformedJSON`, `TestReconnectAfterDisconnect`. 11 of 12 sub-tests fail.

**Evidence:** `.omo/evidence/pipeline-review/task-11-multi-client.txt`

**Impact:** Production multi-client Tauri windows can stall or crash on mid-stream disconnects. The `manager.broadcast` already swallows send errors with `asyncio.gather(..., return_exceptions=True)`, so a single client disconnect does not bring down the backend, but the receive loop is still the point of failure.

**Fix direction (not implemented here):** see `FIX-PLANS-SUMMARY.md` — `fix-websocket-broadcast.md`.

---

### Bug 2 — FrameCache Dedup Is Half-Real (MEDIUM)

**File:** `backend/src/services/frame_cache.py:15-19`

**Root cause:** `read_full()` calls `self._reader.get_flat_dict()` on line 16 before checking whether the elapsed time changed. The dedup check on line 18 returns the cached dict correctly, but the reader has already been invoked.

```python
# backend/src/services/frame_cache.py:15-19 (current behavior)
def read_full(self) -> dict:
    raw = self._reader.get_flat_dict()        # ← ALWAYS called
    et = raw.get("session_running_time", 0.0)
    if et == self._last_et and self._latest is not None and et > 0:
        return self._latest                   # ← cached, but reader already paid
```

The functional behavior is correct (downstream sees stable data, `frame_id` is not double-incremented, the spotter frame is not rebuilt). The performance intent of the dedup — "do not pay the reader cost when nothing changed" — is not realized. The real reader (`lmu_reader.py`) reads from LMU shared memory, which is a cross-process IPC operation. Calling it on every engine tick wastes cycles and contends with LMU's own writes.

**Test that catches it:** `backend/tests/test_frame_cache_flow_e2e.py::TestDedupIsReal::test_same_elapsed_time_reader_called_once`

**Reproduce:**
```python
reader = FakeReader(varying_data=[
    _frame(et=10.0, speed_ms=100.0),
    _frame(et=10.0, speed_ms=200.0),  # would leak if reader called twice
])
cache = FrameCache(reader=reader)
cache.read_full()  # call_count → 1
cache.read_full()  # call_count → 2 (should be 1 if dedup were real)
assert reader.call_count == 1  # FAILS: got 2
assert cache.read_full()["speed_ms"] == 100.0  # FAILS: got 200.0
```

**Evidence:** `.omo/evidence/pipeline-review/task-10-frame-cache.txt`

**Impact:** Wasted IPC calls. Not a correctness bug today, but the same gap will be a correctness bug the day someone changes the reader to mutate global state.

**Fix direction (not implemented here):** see `FIX-PLANS-SUMMARY.md` — `fix-crewchief-pipeline.md` (this bug lives in the same file as the FrameCache cleanup work).

---

### Bug 3 — No React Component Renders CrewChief Alerts (MEDIUM)

**File:** `frontend/src/components/RadioOverlay.tsx:22-31` and `frontend/src/components/ConfigTab.tsx`, `frontend/src/App.tsx`

**Root cause:** The Zustand store has the data. The `useWebSocket` hook has the `onmessage` handler at `useWebSocket.ts:336-358` that calls `pushCrewchiefAlert(...)`, which mutates `state.crewchief.events` and `state.crewchief.latestByCategory`. For high/critical severity the handler also calls `setLatestAlert` and `updateTelemetry({alerts: [...]})`. All that wiring is verified by the Phase 3 test `crewchief-visual.spec.ts` (3 of 3 sub-tests pass, hard assertions on store state are green). The visual surface is the missing piece.

Concretely, `RadioOverlay.tsx:22-31` is a Zustand selector list that does not include `latestAlert`, `crewchief.events`, `crewchief.latestByCategory`, or `telemetry.alerts`. `ConfigTab.tsx` and `App.tsx` do not read crewchief state at all. So the data flows in, the store updates, and nothing renders it.

**Test that catches it:** `frontend/e2e/crewchief-visual.spec.ts` (3 tests, all 3 record `[FINDING] Alert text not visible in DOM` as a soft log; the test does not hard-fail so the store-side signal stays green)

**Evidence:**
- `.omo/evidence/pipeline-review/task-14-crewchief-visual.txt`
- `.omo/evidence/pipeline-review/task-14-crewchief-visual-low.txt`
- `.omo/evidence/pipeline-review/task-14-crewchief-visual-high.txt`
- `.omo/evidence/pipeline-review/task-14-crewchief-visual-critical.txt`

**Impact:** Pilots never see the alerts. The whole point of the CrewChief system is the audio cue (which works) and the visual highlight (which is missing). The store is the data structure for the visual highlight, so the bug is "no consumer of the data structure exists".

**Fix direction (not implemented here):** see `FIX-PLANS-SUMMARY.md` — `fix-crewchief-pipeline.md` (UI renderer lives in the same plan as the runtime fixes).

---

### Bug 4 — CrewChiefRuntime Lifespan Uses Wrong Kwarg For 9 of 12 Events (LOW)

**File:** `backend/src/services/crewchief_loop.py:67-79`

**Root cause:** The runtime's `__init__` registers the 12 events using `ap=audio_player`:

```python
self.engine.register_event("flags_monitor", FlagsMonitor(ap=audio_player))
self.engine.register_event("session_monitor", SessionMonitor(ap=audio_player))
# ... etc, all 12 use ap=
```

Of the 12 event classes, 9 only accept the `audio_player=` kwarg. The lifespan in `src/main.py` calls `init_crewchief(audio_player=...)`, which constructs `CrewChiefRuntime(audio_player=audio_player)`, which then tries to instantiate the 9 broken events with `ap=`. The construction fails inside the thread pool during runtime init, and the backend logs a warning ("CrewChiefV4 init skipped: ConditionsMonitor.__init__() got an unexpected keyword argument 'ap'"). The runtime falls back to a degraded state where events do not fire because their audio_player is None.

**Test that catches it:** `backend/tests/test_crewchief_event_flow_e2e.py` works around the bug by bypassing the lifespan with a `_build_runtime()` helper (see lines 441-480 in that file) and using `ap=audio_player` after monkey-patching the 9 broken `__init__` methods. The test passes in this workaround mode, but the underlying bug is still present in `crewchief_loop.py`.

**Evidence:** `.omo/evidence/pipeline-review/task-7-crewchief-events.txt` (the T7 verdict notes "9 event classes don't accept `ap=` kwarg" as an "API drift" finding; here it is reframed as a runtime bug because it is the reason production never gets events).

**Impact:** Production never gets CrewChief alerts. The whole subsystem is effectively dead in production.

**Fix direction (not implemented here):** see `FIX-PLANS-SUMMARY.md` — `fix-crewchief-pipeline.md`. The fix is to make all 12 events accept `ap=` as an alias for `audio_player=`, or to change `crewchief_loop.py` to pass `audio_player=`.

---

### Bug 5 — Test Pollution in `test_pipeline_deterministic` (LOW)

**File:** `backend/tests/test_pipeline_deterministic.py`

**Root cause:** This test fails when run in the full suite but passes when run standalone. The root cause is shared state between tests in the same pytest process (likely the `event_flags` singleton, the `global_settings.messages` set, or the `_executor` thread pool on a `CrewChiefRuntime` constructed in another test). The F2 verification report explicitly flags this as one of the 6 issues that caused the Code Quality Review to REJECT.

**Test that catches it:** `pytest tests/test_pipeline_deterministic.py -v` passes when run alone. `pytest tests/ -v` fails with a state-leak error.

**Evidence:** Plan reference at `.omo/plans/pipeline-review.md:1098` ("6 test pollution in test_pipeline_deterministic")

**Impact:** False negatives in CI. Either the test is genuinely flaky, or the order of test execution matters. Either way the team cannot trust the full-suite result.

**Fix direction (not implemented here):** see `FIX-PLANS-SUMMARY.md` — `fix-test-hygiene.md`. The fix is to make the test reset all relevant singletons in a fixture, or to mark it with a clear ordering.

---

## Part 2: API Drift Issues (21)

These are the failures in the 22 pre-existing tests that were NOT fixed by Phase 0. Phase 0 fixed 5 categories of API drift (`audio_player` kwarg, `reset_all` alias, `max_rpm`/`num_pitstops` fields, FakeAudioPlayer message lists, engine `tick_async` / `clear_all_state` aliases). The 21 remaining failures are deeper drift between the test author and the impl author. They are not bugs in the production code per se — they are bugs in the test files, which were written for a different version of the production code.

The categories below are reproduced from `.omo/evidence/pipeline-review/task-6-remaining-issues.md`. Each category lists the count, the failing tests, and the fix that would address them.

---

### Category A — Event Class Methods Missing (6 failures)

**What's missing:** Tests call `event.play_message(m)` and `event.play_message_immediately(m)` directly on event objects. `AbstractEvent` exposes `play()` and `play_imm()` but not `play_message` or `play_message_immediately`.

**Affected tests:**

| File | Line | Test |
|------|------|------|
| `backend/tests/test_tyre_monitor.py` | (around) `test_..._fires_via_play_message` | 2 tests |
| `backend/tests/test_battery.py` | (around) `test_..._fires_via_play_message` | 2 tests |
| `backend/tests/test_frozen_order_monitor.py` | (around) `test_..._fires_via_play_message_immediately` | 1 test |
| `backend/tests/test_pit_stops.py` | (around) `test_pit_request_emits_message` (calls `is_applicable` not `applicable`) | 1 test |

**Fix:**
```python
# in backend/src/intelligence/base_event.py, AbstractEvent class
play_message = play
play_message_immediately = play_imm
is_applicable = applicable
```

The T7 test (`test_crewchief_event_flow_e2e.py`) already does this at runtime via monkey-patch (see lines 92-99). Lifting it into the source file is the cleanest fix.

---

### Category B — EventFlags Fields Missing (4 failures)

**What's missing:** Two flag fields referenced by event files but not declared on the `event_flags` singleton.

**Affected tests:**

| Field needed | Used by | Tests |
|--------------|---------|-------|
| `is_pitting_this_lap: bool = False` | `backend/src/intelligence/events/fuel.py:48` | 2 tests |
| `waiting_for_driver_is_ok_response: bool = False` | `backend/src/intelligence/events/damage_reporting.py:72` | 2 tests |

**Fix:**
```python
# in backend/src/intelligence/event_flags.py, EventFlags class
class EventFlags:
    is_pitting: bool = False
    waiting_driver_ok: bool = False
    # ADD:
    is_pitting_this_lap: bool = False
    waiting_for_driver_is_ok_response: bool = False
    # ... existing fields
```

Or rename the existing fields if the old names were typos. The T7 test patches these at runtime (see lines 107-111 of `test_crewchief_event_flow_e2e.py`); the production fix is the same, lifted into source.

---

### Category C — Model Fields Missing (8 failures)

**What's missing:** Three fields on `GameStateData` subclasses that event files reference but are not declared.

**Affected tests:**

| Field needed | Where on GSD | Used by | Tests |
|--------------|--------------|---------|-------|
| `weather: Any = None` | top-level | `conditions_monitor.py`, integration | 4 tests |
| `track_definition: Any = None` | `SessionData` | `pit_stops.py` | 2 tests |
| `overheating: bool = False` | `EngineData` | `engine_monitor.py` | 2 tests |

**Fix:**
```python
# in backend/src/models/game_state_data.py
@dataclass
class GameStateData:
    # ... existing fields
    weather: Any = None  # NEW

@dataclass
class SessionData:
    # ... existing fields
    track_definition: Any = None  # NEW

@dataclass
class EngineData:
    # ... existing fields
    overheating: bool = False  # NEW
```

The T7 test sets these dynamically via `setattr()` (see lines 407, 424, 431 in `test_crewchief_event_flow_e2e.py`). The clean fix is to declare them so `setattr` is not needed.

---

### Category D — Logic-Level Issues (2 failures)

**What's wrong:** Two tests that exercise real event logic, not just API shape. These need investigation, not a one-line fix.

**Affected tests:**

| Test | Symptom | Root cause |
|------|---------|-----------|
| `backend/tests/test_crewchief_pipeline.py::TestEventSequenceOrder::test_events_dispatch_in_correct_sequence` | "Secuencias duplicadas: [5, 5, 7, 10, 15, 20, 20, 25, 30, 30, 35, 40]" | Two events have the same sequence number (5, 20, 30). Likely a registration order issue in `crewchief_loop.py:68-79` or in `event_engine.py` sequence assignment. |
| `backend/tests/test_crewchief_pipeline.py::TestEndToEndPipeline::test_45_tick_race_simulation` | "No fuel messages in ticks 6-15" | Fuel event not firing in the test scenario. Either the test fixture builds frames that do not cross the fuel threshold, or the fuel trigger condition has a logic gap. |

**Fix:** Both require reading the event registration code and the test fixture together. There is no obvious one-line patch.

---

### Category E — Test Infrastructure (1 failure)

**What's wrong:** The session reset test still fails after the T3 alias fix.

**Affected test:** `backend/tests/test_crewchief_integration.py::TestSessionReset::test_clear_all_resets_everything`

**Root cause hypothesis:** The test expects all 12 events to reset their internal state, but maybe not all of them override `_reset` (or the equivalent). The fix is either to add a `_reset` method to the events that lack one, or to relax the test to assert on the events that do.

---

## Cross-References

- `FIX-PLANS-SUMMARY.md` — overview of the three fix plans that will resolve Bugs 1 through 5
- `TEST-STRATEGY.md` — why these bugs were invisible to the old tests
- `LLM-MIGRATION.md` — Categories B, C, and the LLM impact overlap; the migration will touch `llm_client.py` and several `.env` keys
- `.omo/evidence/pipeline-review/task-6-remaining-issues.md` — original evidence file with the 21-failure analysis
- `.omo/evidence/pipeline-review/task-7-crewchief-events.txt` — T7 evidence with the 10 new API drift findings that overlapped with the Bug 4 root cause

---

## Summary Table

| # | Type | Severity | File:Line | Caught by |
|---|------|----------|-----------|-----------|
| 1 | Bug | HIGH | `backend/src/routers/websocket.py:250-285` | `test_ws_multi_client_e2e.py` (11/12 fail) |
| 2 | Bug | MEDIUM | `backend/src/services/frame_cache.py:15-19` | `test_frame_cache_flow_e2e.py::TestDedupIsReal` |
| 3 | Bug | MEDIUM | `frontend/src/components/RadioOverlay.tsx:22-31` (selector) | `e2e/crewchief-visual.spec.ts` (soft finding) |
| 4 | Bug | LOW | `backend/src/services/crewchief_loop.py:67-79` | `test_crewchief_event_flow_e2e.py` (workaround) |
| 5 | Bug | LOW | `backend/tests/test_pipeline_deterministic.py` | Full-suite run (F2 REJECT) |
| A | Drift | — | `base_event.py` (missing aliases) | 6 pre-existing tests |
| B | Drift | — | `event_flags.py` (missing fields) | 4 pre-existing tests |
| C | Drift | — | `game_state_data.py` (missing fields) | 8 pre-existing tests |
| D | Drift | — | `crewchief_loop.py` + fixture | 2 pre-existing tests |
| E | Drift | — | `test_crewchief_integration.py` | 1 pre-existing test |
