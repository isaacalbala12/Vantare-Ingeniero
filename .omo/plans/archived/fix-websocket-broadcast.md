# Fix WebSocket Broadcast — Bug 3

## TL;DR

> **Quick Summary**: Fix the WebSocket multi-client broadcast flow. The current starlette `WebSocket` implementation doesn't support multiple `receive()` calls after disconnect, which breaks the test pattern AND the production pattern for 3+ simultaneous clients, disconnect-mid-broadcast, and reconnect cycles. Root cause is likely in the broadcast path (manager.broadcast swallows exceptions or skips clients silently).
>
> **Deliverables**:
> - Root-cause fix in `backend/src/routers/websocket.py` (or `backend/src/transport/broadcaster.py`)
> - Possibly: refactor to use `asyncio` task-based broadcast that survives disconnects
> - `test_ws_multi_client_e2e.py` passes 11/12 → 12/12
> - 1 commit on `feature/benchmark-llm`
>
> **Estimated Effort**: Medium (2-3 hours)
> **Parallel Execution**: NO — investigation then fix
> **Critical Path**: Investigation → Fix → Verify
> **Type**: PROPER-FIX (root cause, not quick patch)

## Context

### Original Request
Fix the WebSocket broadcast pattern so multiple clients can connect, receive broadcasts, disconnect without crashing the server, and reconnect.

### Research Findings
See `docs/pipeline-review/BUGS.md` (Bug #3 section). Key references:
- `docs/pipeline-review/evidence/pipeline-review/task-11-multi-client.txt` documents 11/12 failures
- `docs/pipeline-review/evidence/pipeline-review/task-7-crewchief-events.txt` mentions WS receive workaround
- The error pattern: `RuntimeError: Cannot call "receive" once a disconnect message has been received.`
- The F2 audit also flagged: "WS broadcast fixture does not install telemetry_reader / strategy_service on app.state"

### Metis Review
**Decisions confirmed by user**:
- Proper-fix approach
- One plan per category (this is category 2 of 3)
- Test pollution is in separate plan
- LLM migration is separate

---

## Work Objectives

### Core Objective
Multiple WS clients must work correctly: receive all broadcasts, handle mid-broadcast disconnects, reconnect after disconnect, and tolerate malformed input — all without crashing the server or starving other clients.

### Definition of Done
- [ ] `test_ws_multi_client_e2e.py` passes 12/12 (was 1/12)
- [ ] 3+ clients can connect and all receive identical broadcasts
- [ ] 1 client disconnecting doesn't crash server or starve others
- [ ] Malformed JSON doesn't crash server
- [ ] Reconnect after disconnect works

### Must Have
- Real root-cause investigation (proper-fix mandate)
- No shotgun patches (one per test, fix root cause)
- All 4 test classes pass: TestThreeClientsAllReceive, TestDisconnectMidBroadcast, TestMalformedJSON, TestReconnectAfterDisconnect
- Existing WS message format unchanged (broadcast content must match current)

### Must NOT Have (Guardrails)
- NO new pip/npm dependencies
- NO breaking changes to existing WS message format
- NO `print()` in production code (use logging)
- NO `as any` in TS test code if it can be avoided (already noted in F4)

---

## Verification Strategy (MANDATORY)

### Test Strategy
- Investigation task creates a minimal 3-client repro that demonstrates the failure
- Fix task verifies ALL 4 test classes pass
- No regression: existing `test_ws_integration.py` must still pass
- No regression: `test_crewchief_event_flow_e2e.py` (which uses WS) must still pass

### QA Policy
After fix:
- `cd backend && pytest tests/test_ws_multi_client_e2e.py -v 2>&1 | tail -20` — all 12 pass
- `cd backend && pytest tests/test_ws_integration.py -v 2>&1 | tail -10` — no regression
- `cd backend && pytest tests/test_crewchief_event_flow_e2e.py -q 2>&1 | tail -5` — no regression

---

## Execution Strategy

### Dependency Graph

```
[Task 1: Investigate root cause] → [Task 2: Implement fix] → [Task 3: Verify no regression]
```

### Waves

```
Wave 1: Investigation + Fix (sequential):
├── Task 1: Investigate WebSocket receive pattern root cause
└── Task 2: Fix the root cause in broadcast path

Wave 2: Verification + Cleanup:
├── Task 3: Fix WS fixture setup (app.state telemetry_reader)
└── Task 4: Verify no regression in other E2E tests

Final Wave: F1-F4
```

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> **DO NOT skip investigation** — proper-fix mandate.

---

## WAVE 1: Investigation + Fix

- [ ] 1. Investigate WebSocket receive pattern root cause

  **What to do**:
  1. Read `backend/src/routers/websocket.py:50-120` — `ConnectionManager.broadcast()` and `connect/disconnect`
  2. Read `backend/src/transport/broadcaster.py` — wrapper around `broadcast_sync`
  3. Run the failing test: `cd backend && pytest tests/test_ws_multi_client_e2e.py::TestThreeClientsAllReceive::test_three_clients_get_identical_broadcast -v --tb=long 2>&1 | tail -40`
  4. Check `app.state` setup: does the test fixture install `telemetry_reader` and `strategy_service`? The F2 audit flagged: "WS broadcast fixture does not install telemetry_reader / strategy_service on app.state"
  5. Check if `manager.broadcast()` is wrapped in try/except that swallows errors
  6. Check the starlette `WebSocket` docs: what methods are available after disconnect?
  7. Check if there's a task/queue mechanism that allows async delivery
  8. Identify the EARLIEST point where the message is lost
  9. Document findings in `.omo/notepads/fix-websocket-broadcast/learnings.md`

  **Must NOT do**:
  - Do NOT fix yet (just investigate)
  - Do NOT change the WS message format

  **Recommended Agent Profile**:
  - **Category**: `deep` — multi-file trace, async WS behavior analysis
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (Wave 1 sequential)
  - **Blocked By**: None

  **References**:
  - `backend/src/routers/websocket.py` — ConnectionManager
  - `backend/src/transport/broadcaster.py` — broadcast wrapper
  - `backend/tests/test_ws_multi_client_e2e.py` — 4 test classes, 12 sub-tests
  - `backend/tests/test_ws_integration.py` — existing WS tests (must not regress)
  - `docs/pipeline-review/evidence/pipeline-review/task-11-multi-client.txt`
  - `docs/pipeline-review/BUGS.md` (Bug #3)

  **Acceptance Criteria**:
  - [ ] Root cause identified in writing
  - [ ] Why 3+ clients don't all receive: documented
  - [ ] Why disconnect crashes: documented
  - [ ] Why malformed JSON breaks: documented
  - [ ] Whether `app.state` setup is the cause: confirmed

  **Evidence**: `.omo/notepads/fix-websocket-broadcast/learnings.md` (T1 section)

---

- [ ] 2. Fix the root cause in the broadcast path

  **What to do**:
  1. Based on Task 1's root cause, implement the specific fix
  2. Most likely candidates (in order of probability):
     - a) `ConnectionManager.broadcast()` doesn't await per-client send (sync exception kills the loop) → wrap each client send in try/except + asyncio.gather with return_exceptions=True
     - b) `app.state` missing `telemetry_reader`/`strategy_service` → fixture must install them OR `WebSocketHub.broadcast` must tolerate absence
     - c) starlette's `WebSocket` doesn't support re-receive after disconnect → use a per-client task/queue, or use `asyncio.create_task` for send
     - d) `manager.broadcast()` skips dead connections silently → maintain `active_connections: set` and `discard` on send failure
  3. Implement the MINIMAL fix that addresses the root cause
  4. Verify: `cd backend && pytest tests/test_ws_multi_client_e2e.py -v --tb=short 2>&1 | tail -20`

  **Must NOT do**:
  - Do NOT change the WS message format
  - Do NOT add a new endpoint
  - Do NOT add a new dependency

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — careful WS code change
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on T1)
  - **Blocked By**: 1

  **References**:
  - Task 1's findings
  - `backend/src/routers/websocket.py`

  **Acceptance Criteria**:
  - [ ] `test_ws_multi_client_e2e.py` passes 12/12
  - [ ] Fix is minimal (≤20 lines changed)
  - [ ] WS message format unchanged

  **Commit**: YES
  - Message: `fix(websocket): proper broadcast for multi-client + disconnect handling`
  - Files: depends on root cause (likely `websocket.py` or `broadcaster.py`)

  **Evidence**: `.omo/notepads/fix-websocket-broadcast/learnings.md` (T2 section)

---

## WAVE 2: Fixture + No-Regression

- [ ] 3. Fix WS test fixture (app.state telemetry_reader/strategy_service)

  **What to do**:
  1. Locate the WS test fixture in `backend/tests/test_ws_multi_client_e2e.py`
  2. Check if it creates a real `app` and what state it sets up
  3. If `app.state.telemetry_reader` and `app.state.strategy_service` are missing, install them (use `FakeReader` + `FakeStrategyService` or similar)
  4. Verify: `cd backend && pytest tests/test_ws_multi_client_e2e.py -v --tb=short 2>&1 | tail -10`

  **Must NOT do**:
  - Do NOT mock the broadcast itself
  - Do NOT skip the fixture setup

  **Recommended Agent Profile**:
  - **Category**: `quick` — small fixture fix
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T4)
  - **Parallel Group**: Wave 2
  - **Blocked By**: 2

  **References**:
  - F2 audit: "WS broadcast fixture does not install telemetry_reader / strategy_service on app.state"
  - `backend/tests/test_ws_multi_client_e2e.py` — fixture location

  **Acceptance Criteria**:
  - [ ] `app.state.telemetry_reader` set in fixture
  - [ ] `app.state.strategy_service` set in fixture
  - [ ] No more "X not found in app state" warnings in test output

  **Evidence**: `.omo/notepads/fix-websocket-broadcast/learnings.md` (T3 section)

---

- [ ] 4. Verify no regression in other E2E tests

  **What to do**:
  1. Run full Phase 1 E2E suite: `cd backend && pytest tests/test_crewchief_event_flow_e2e.py tests/test_spotter_flow_e2e.py tests/test_strategy_flow_e2e.py tests/test_frame_cache_flow_e2e.py tests/test_ws_multi_client_e2e.py -q 2>&1 | tail -10`
  2. Run pre-existing: `cd backend && pytest tests/test_ws_integration.py tests/test_crewchief_pipeline.py tests/test_crewchief_integration.py -q 2>&1 | tail -5`
  3. Document any new failures
  4. If regressions, investigate (could be that the broadcast fix changed behavior)

  **Must NOT do**:
  - Do NOT mark complete if any regression

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low` — verification only
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T3)
  - **Parallel Group**: Wave 2
  - **Blocked By**: 2, 3

  **References**:
  - All Phase 1 E2E tests

  **Acceptance Criteria**:
  - [ ] No regression in any E2E test
  - [ ] No regression in pre-existing tests

  **Commit**: NO (verification only, or amend T2 commit if changes needed)

  **Evidence**: `.omo/notepads/fix-websocket-broadcast/learnings.md` (T4 section)

---

## Final Verification Wave (MANDATORY)

> 4 review agents run in PARALLEL after the fix is done.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Verify: 1 commit, 12/12 WS tests pass, no regression, no scope creep.
  Output: `Commits [1/1] | Tests [12/12] | No regression | VERDICT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run: `pytest tests/test_ws_multi_client_e2e.py tests/test_ws_integration.py tests/test_crewchief_event_flow_e2e.py`. Check anti-patterns.
  Output: `Build | Lint | Tests | Files | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Run all 4 test classes. Edge case: 5 clients, rapid disconnects, broadcast during reconnect window.
  Output: `Tests [12/12] | Edge Cases [N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  Verify: fix is minimal, no mocking abuse, message format unchanged.
  Output: `Tests [N/N honest] | Mocking [clean] | Scope [contained] | VERDICT`

---

## Commit Strategy

- **Single commit**: `fix(websocket): proper broadcast for multi-client + disconnect handling`

---

## Success Criteria

### Verification Commands
```bash
# After fix
cd backend && pytest tests/test_ws_multi_client_e2e.py -v --tb=short 2>&1 | tail -20
cd backend && pytest tests/test_ws_integration.py -v 2>&1 | tail -10
cd backend && pytest tests/test_crewchief_event_flow_e2e.py -q 2>&1 | tail -5
```

### Final Checklist
- [ ] `test_ws_multi_client_e2e.py` passes 12/12
- [ ] No regression in `test_ws_integration.py`
- [ ] No regression in `test_crewchief_event_flow_e2e.py`
- [ ] All F1-F4 APPROVED
- [ ] 1 commit on `feature/benchmark-llm`
- [ ] No new dependencies
