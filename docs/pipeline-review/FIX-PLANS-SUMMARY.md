# Fix Plans Summary

**Purpose:** Overview of the three fix plans that will resolve the 5 real production bugs the test review surfaced. Each plan has a scope, expected outcome, dependencies, and risk level. The full plans will be written in a separate session; this doc is the index.

The five bugs and their mapping to the three plans:

| Bug | Plan |
|-----|------|
| Bug 1: WS receive pattern (HIGH) | `fix-websocket-broadcast.md` |
| Bug 2: FrameCache dedup (MEDIUM) | `fix-crewchief-pipeline.md` |
| Bug 3: No crewchief alert renderer (MEDIUM) | `fix-crewchief-pipeline.md` |
| Bug 4: CrewChiefRuntime lifespan wrong kwarg (LOW) | `fix-crewchief-pipeline.md` |
| Bug 5: Test pollution in `test_pipeline_deterministic` (LOW) | `fix-test-hygiene.md` |

The three plans are independent except for the dependency noted below.

---

## Plan 1: `fix-crewchief-pipeline.md`

**Scope:** Bugs 2, 3, and 4. Touches the CrewChief pipeline end-to-end: the runtime initialization, the frame cache, and the React renderer.

### Files to modify

- `backend/src/services/frame_cache.py` — fix the dedup so the reader is called only when ET changes (Bug 2)
- `backend/src/services/crewchief_loop.py:67-79` — change `ap=audio_player` to `audio_player=audio_player` (Bug 4)
- `frontend/src/components/RadioOverlay.tsx:22-31` — add a new renderer for crewchief alerts (Bug 3)
- Optionally: a new `frontend/src/components/CrewchiefBanner.tsx` or `CrewchiefFeed.tsx` if the renderer does not fit in `RadioOverlay`

### Files to add (test updates)

- `backend/tests/test_crewchief_event_flow_e2e.py` — remove the runtime monkey-patches at lines 78-181 once the source files support the API directly
- `backend/tests/test_frame_cache_flow_e2e.py::TestDedupIsReal::test_same_elapsed_time_reader_called_once` — should now pass (was the failing test for Bug 2)
- `frontend/e2e/crewchief-visual.spec.ts` — promote the soft DOM check to a hard `expect(...).toBeVisible()`

### Expected outcome

- All 12 T7 sub-tests pass with no runtime monkey-patches (down from 8 workarounds).
- The T7 verifier runs the production `CrewChiefRuntime.__init__` successfully (no degraded fallback).
- FrameCache dedup is real: same ET = no reader call, different ET = reader called once.
- The frontend DOM shows the crewchief alert text when a `crewchief_alert` WS frame is received.
- The T14 hard assertions all pass; no soft findings logged.

### Dependencies

None. This plan is self-contained. The runtime patches in T7 mean the test will fail loudly if the source fix is wrong, so this is a low-risk change with a strong safety net.

### Risk

Low. The runtime monkey-patches in `test_crewchief_event_flow_e2e.py` are exactly the workarounds that the source fix eliminates. If the source fix is incomplete (e.g. one event class still does not accept `audio_player=`), the test fails immediately with a clear error.

The frontend renderer change is a UI addition. If the renderer does not match the expected behavior, the T14 test fails on the `expect(domVisible).toBe(true)` assertion. The risk is visual: the renderer may need CSS tuning to match the existing dashboard.

The FrameCache dedup fix has one subtle pitfall: the dedup check currently relies on `self._last_et` from the previous call. If the first call has ET=0, the second call's ET is also 0, the dedup is bypassed (correctly, per the test). If the second call has a positive ET, the cache returns the latest, but the latest was set when the first call was made (with ET=0). So we need to be careful: the cached dict should be invalidated when ET transitions from 0 to a positive value. The recommended fix is to cache ET alongside `_latest` and only return the cached dict when both ETs match and the cached ET is positive.

---

## Plan 2: `fix-websocket-broadcast.md`

**Scope:** Bug 1. Touches the WebSocket receive pattern in `backend/src/routers/websocket.py:250-285`.

### Files to modify

- `backend/src/routers/websocket.py:250-285` — replace the single `await websocket.receive()` loop with a more robust pattern

### Files to add (test updates)

- `backend/tests/test_ws_multi_client_e2e.py` — all 12 sub-tests should now pass; no test changes needed beyond verification
- Optionally: add new tests for edge cases the current 12 do not cover (e.g., 5+ simultaneous clients, very rapid disconnect cycles)

### Expected outcome

- 3 simultaneous clients all receive the same broadcast.
- Mid-broadcast disconnect does not crash the backend or starve the other clients.
- Malformed JSON from one client does not affect others.
- Reconnect after disconnect works.
- The Starlette `RuntimeError: Cannot call "receive" once a disconnect message has been received` is gone.

### Dependencies

None on Plan 1 or Plan 3. This plan is fully self-contained.

### Risk

Medium. WebSocket patterns are subtle, and the current code is production-tested (it works in the dev env, just not under TestClient). The fix needs to:
- Continue handling binary MessagePack telemetry frames
- Continue handling JSON `telemetry` and `pilot_question` events
- Continue handling malformed JSON gracefully
- Handle the disconnect race (handler's `finally` block still running when next broadcast arrives)
- Be compatible with both the production deployment (real starlette/FastAPI) and the TestClient

The recommended fix direction is to split the receive into two coroutines: one for binary telemetry, one for JSON control. Use `await websocket.receive_text()` and `await websocket.receive_bytes()` in separate tasks. Each can fail independently without affecting the other.

A more conservative fix is to wrap the current pattern in a `try/except RuntimeError` that logs the disconnect and exits the loop. This is less clean but lower risk.

The T11 test will validate the fix by passing all 12 sub-tests. If the fix regresses, the test fails immediately.

---

## Plan 3: `fix-test-hygiene.md`

**Scope:** Bug 5 plus the 22/22 pre-existing tests goal, plus the unauthorized npm deps and the `@ts-ignore` cleanups.

### Files to modify

- `backend/tests/test_pipeline_deterministic.py` — fix the test pollution by resetting singletons in a fixture (Bug 5)
- `backend/src/intelligence/base_event.py` — add `play_message = play` and `play_message_immediately = play_imm` aliases (Category A from `BUGS.md`)
- `backend/src/intelligence/base_event.py` — add `is_applicable = applicable` alias (Category A)
- `backend/src/intelligence/event_flags.py` — add `is_pitting_this_lap` and `waiting_for_driver_is_ok_response` fields (Category B)
- `backend/src/models/game_state_data.py` — add `weather: Any = None` to `GameStateData`, `track_definition: Any = None` to `SessionData`, `overheating: bool = False` to `EngineData` (Category C)
- `frontend/package.json` — remove `@testing-library/react` and `happy-dom` if they were added without authorization (F4 violation noted in `.omo/plans/pipeline-review.md:1106`)
- `frontend/src/__tests__/appStore.test.ts`, `useWebSocket.test.ts` — re-check for any new `@ts-ignore` introduced during the review

### Files to add (test updates)

- `backend/tests/test_crewchief_pipeline.py`, `test_crewchief_integration.py` — the 21 remaining failures should now be green (Categories A, B, C fixes resolve 18 of 21; the 3 logic-level and test-infra failures need separate work)
- `backend/tests/test_pipeline_deterministic.py` — should now pass in the full suite

### Expected outcome

- 22 (or more) of the 24 pre-existing tests pass.
- Test pollution in `test_pipeline_deterministic` is fixed.
- No unauthorized npm dependencies in `frontend/package.json`.
- No new `@ts-ignore` in frontend source files (the 8 in `frontend/e2e/` are documented and allowed).

### Dependencies

None on Plan 1 or Plan 2. This plan is fully self-contained.

### Risk

Low. The API drift fixes (Categories A, B, C) are all small field or method additions with no breaking changes. The test pollution fix is a fixture addition. The npm dep cleanup is a `package.json` revert.

The 3 logic-level failures (Category D) and the 1 test-infra failure (Category E) are deferred — they need deeper investigation, not API additions. The plan should make this explicit and not try to grind through them.

---

## Execution Order

The three plans can be executed in any order. Suggested order for minimum disruption:

1. **Plan 3 first** (smallest, lowest risk, fixes the 22/22 pre-existing tests goal). Once Categories A, B, C are in source, the T7 test can drop its runtime monkey-patches naturally.
2. **Plan 1 second** (Bugs 2, 3, 4). The runtime fix is a one-liner; the renderer is a UI addition; the FrameCache dedup is a small refactor.
3. **Plan 2 third** (Bug 1, the most subtle). The WebSocket pattern fix is independent of the other two, but doing it last means the T11 test runs against a clean CrewChief pipeline.

The review left 3 commits on the branch:

```
6ac49b7  test(frontend): Phase 3 Playwright E2E for 4 critical user paths
4486362  test(e2e): Phase 1 backend E2E workflow tests for 4 critical paths
c295dcc  fix(events): Phase 0 API drift fixes for pre-existing crewchief tests
```

The three fix plans should each produce 1-2 commits following the existing commit style:

```
fix(crewchief): lift API drift aliases into source (Categories A, B, C)
fix(frame_cache): real dedup — reader called only when ET changes
fix(crewchief_loop): use audio_player= kwarg consistently
feat(ui): render crewchief alerts in RadioOverlay
fix(websocket): split receive into text+bytes coroutines
test(ws): all 12 multi-client tests now pass
chore(test): fix test pollution in test_pipeline_deterministic
chore(deps): remove unauthorized @testing-library/react and happy-dom
```

---

## Full Plans Location

The full implementation plans (with file-by-file diffs and step-by-step instructions) will be written at:

- `.omo/plans/fix-crewchief-pipeline.md` — for Plan 1
- `.omo/plans/fix-websocket-broadcast.md` — for Plan 2
- `.omo/plans/fix-test-hygiene.md` — for Plan 3

This file is the index. The full plans are the implementation guides.

---

## Cross-References

- `BUGS.md` — the bugs each plan resolves
- `TEST-INVENTORY.md` — which tests will pass after each plan
- `ARCHITECTURE.md` — which boxes in the pipeline diagram each plan touches
- `LLM-MIGRATION.md` — independent of these plans; LLM work happens in a separate effort
