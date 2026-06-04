# Fix CrewChief Pipeline — Bugs 1+2+4

## TL;DR

> **Quick Summary**: Fix 3 of the 5 real bugs detected by the pipeline-review E2E tests. The CrewChief event pipeline is broken: events don't fire (Bug 1), the data cache that feeds them is half-real (Bug 2), and even if events did fire, no UI component renders them (Bug 4). All three must be fixed together because they form a single chain (TelemetryFrame → FrameCache → EventEngine → AudioPlayer → WS → Frontend store → DOM).
>
> **Deliverables**:
> - `backend/src/services/crewchief_loop.py` — Root-cause fix for why `process_tick()` doesn't emit alerts
> - `backend/src/services/frame_cache.py` — Proper dedup (don't call reader when et unchanged)
> - `frontend/src/components/RadioOverlay.tsx` (or new component) — Renders `crewchief.events` with severity styling
> - 3 commits, one per bug, on `feature/benchmark-llm`
>
> **Estimated Effort**: Short-Medium (3-5 hours)
> **Parallel Execution**: NO — Bug 2 must land first (data path), then Bug 1 (events), then Bug 4 (UI)
> **Critical Path**: Bug 2 (FrameCache) → Bug 1 (CrewChiefRuntime) → Bug 4 (UI renderer)
> **Type**: PROPER-FIX (root cause, not quick patch)

## Context

### Original Request
Fix the 3 bugs that block the core CrewChief event flow: alerts don't fire, the cache feeding them is broken, and the UI doesn't render them.

### Research Findings
See `docs/pipeline-review/BUGS.md` for the full bug catalog and `docs/pipeline-review/ARCHITECTURE.md` for the data flow. Key references:
- `docs/pipeline-review/learnings.md` (in notepad) has 695 lines of detailed subagent findings
- `docs/pipeline-review/evidence/pipeline-review/task-7-crewchief-events.txt` documents the 12/12 failures
- `docs/pipeline-review/evidence/pipeline-review/task-10-frame-cache.txt` documents the dedup bug
- `docs/pipeline-review/evidence/pipeline-review/task-14-crewchief-visual.txt` documents the missing UI renderer

### Metis Review
**Decisions confirmed by user**:
- Proper-fix approach (root cause, not patch)
- One plan per category (this is category 1 of 3)
- Test pollution (Bug 5) and WS receive (Bug 3) are in separate plans
- LLM migration is a separate workstream (NOT in this plan)

---

## Work Objectives

### Core Objective
The CrewChief event pipeline must work end-to-end: a `TelemetryFrame` arrives → events fire → alerts are emitted to the WS → frontend store updates → UI renders the alert with severity styling.

### Definition of Done
- [ ] `test_crewchief_event_flow_e2e.py` passes 12/12 (was 0/12)
- [ ] `test_frame_cache_flow_e2e.py` passes 8/8 (was 7/8)
- [ ] `crewchief-visual.spec.ts` shows alerts visible in DOM (was store-only)
- [ ] No regressions in T8 (spotter), T9 (strategy), T11 (WS pattern tests)

### Must Have
- Real root cause investigation before fixing (no shotgun patches)
- Each fix verified by its corresponding E2E test
- No modifications to event business logic beyond what's needed for the fix
- New UI component follows existing patterns in `frontend/src/components/`

### Must NOT Have (Guardrails)
- NO new pip/npm dependencies
- NO mocking of internal components in tests
- NO LLM/PTT workflow changes (separate migration)
- NO breaking changes to existing WS message format (only ADD capability)
- NO `as any` / `@ts-ignore` in production code (frontend components)

---

## Verification Strategy (MANDATORY)

### Test Strategy
- After each bug fix, run ONLY the relevant test file to verify the fix
- After all 3 bugs fixed, run the full Phase 1 backend suite to check for regressions
- No need to re-run Phase 3 (Playwright) until Bug 4 is done

### QA Policy
Each bug fix MUST include:
- Investigation: why does the current code fail the test?
- Fix: minimum change to address root cause
- Verification: run the corresponding test, all pass
- Evidence: append to `.omo/notepads/fix-crewchief-pipeline/learnings.md`

---

## Execution Strategy

### Dependency Graph

```
[Bug 2: FrameCache] → [Bug 1: CrewChiefRuntime] → [Bug 4: UI Renderer]
   (data path)            (event firing)             (DOM display)
```

- Bug 2 first because events read from FrameCache — if cache is broken, fixing events alone won't help
- Bug 1 second because UI depends on events firing
- Bug 4 last because it depends on events actually firing

### Waves

```
Wave 1 (Bug 2: FrameCache dedup):
├── Task 1: Investigate FrameCache dedup root cause
└── Task 2: Fix FrameCache.read_full() to skip reader on dedup hit

Wave 2 (Bug 1: CrewChiefRuntime):
├── Task 3: Investigate why CrewChiefRuntime.process_tick() doesn't emit alerts
└── Task 4: Fix CrewChiefRuntime (root cause: event suppression? missing handler?)

Wave 3 (Bug 4: UI Renderer):
├── Task 5: Design RadioOverlay changes to render crewchief.events
└── Task 6: Implement + verify DOM assertions

Final Wave (F1-F4):
├── F1: Plan Compliance Audit
├── F2: Code Quality Review
├── F3: Real Manual QA (run all 3 test files)
└── F4: Scope Fidelity Check
```

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> Each bug has 2 tasks: investigate (1) + fix (1).
> **DO NOT skip investigation** — root-cause analysis is the proper-fix mandate.

---

## WAVE 1: Bug 2 — FrameCache dedup (data path)

- [ ] 1. Investigate FrameCache dedup root cause

  **What to do**:
  1. Read `backend/src/services/frame_cache.py:15-44` carefully
  2. Run the failing test: `cd backend && pytest tests/test_frame_cache_flow_e2e.py::TestDedupIsReal::test_same_elapsed_time_reader_called_once -v --tb=long`
  3. Trace: what is `_latest`, `_last_et`, `_frame_id`, `_spotter`? When is each updated?
  4. Identify root cause: WHY does the test expect `call_count == 1` but current code calls reader twice?
  5. Read `backend/src/services/lmu_reader.py` (or equivalent) to understand if the reader is cheap (cached internally) or expensive (IPC to LMU game)
  6. Document findings in `.omo/notepads/fix-crewchief-pipeline/learnings.md` with: current behavior, expected behavior, gap

  **Must NOT do**:
  - Do NOT fix yet (just investigate)
  - Do NOT modify the test (test is correct per proper-fix mandate)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low` — read + trace + document
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T3, T5)
  - **Parallel Group**: Wave 1
  - **Blocked By**: None

  **References**:
  - `backend/src/services/frame_cache.py:15-22` — the buggy read_full
  - `backend/tests/test_frame_cache_flow_e2e.py:119-150` — failing test
  - `docs/pipeline-review/BUGS.md` (Bug #2 section)
  - `docs/pipeline-review/evidence/pipeline-review/task-10-frame-cache.txt`

  **Acceptance Criteria**:
  - [ ] Root cause identified in writing (not just "it's broken")
  - [ ] Findings saved to notepad
  - [ ] Recommendation: how to fix (in 1-2 lines)

  **Evidence**: `.omo/notepads/fix-crewchief-pipeline/learnings.md` (T1 section)

---

- [ ] 2. Fix FrameCache.read_full() to skip reader on dedup hit

  **What to do**:
  1. Based on Task 1's root cause analysis, implement the fix
  2. Most likely fix: add optional `elapsed_time: float = None` parameter to `read_full()`; if provided AND matches `_last_et` AND `_latest is not None` AND `> 0`, return cached without calling reader
  3. The reader call (`self._reader.get_flat_dict()`) must move INSIDE the dedup-miss branch
  4. Verify: `cd backend && pytest tests/test_frame_cache_flow_e2e.py -v --tb=short 2>&1 | tail -15`
  5. Verify: `cd backend && pytest tests/test_frame_cache.py -v --tb=short 2>&1 | tail -10` (existing tests must still pass)
  6. Verify: full E2E suite doesn't regress — `cd backend && pytest tests/test_crewchief_event_flow_e2e.py tests/test_spotter_flow_e2e.py tests/test_strategy_flow_e2e.py -q 2>&1 | tail -5`

  **Must NOT do**:
  - Do NOT remove the existing public API
  - Do NOT change the signature of `get_spotter_frame()`
  - Do NOT add caching that persists across `FrameCache` instances

  **Recommended Agent Profile**:
  - **Category**: `quick` — 1-2 line code change once root cause is known
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on T1)
  - **Blocked By**: 1

  **References**:
  - Task 1's findings
  - `backend/src/services/frame_cache.py:15-44` — current implementation

  **Acceptance Criteria**:
  - [ ] `test_frame_cache_flow_e2e.py::TestDedupIsReal::test_same_elapsed_time_reader_called_once` passes
  - [ ] `test_frame_cache.py` (existing 15 tests) still passes
  - [ ] No regression in other E2E tests

  **Commit**: YES
  - Message: `fix(frame_cache): proper dedup — skip reader when elapsed_time unchanged`
  - Files: `backend/src/services/frame_cache.py`

  **Evidence**: `.omo/notepads/fix-crewchief-pipeline/learnings.md` (T2 section)

---

## WAVE 2: Bug 1 — CrewChiefRuntime doesn't emit alerts

- [ ] 3. Investigate CrewChiefRuntime why events don't fire from injected TelemetryFrame

  **What to do**:
  1. Read `backend/src/services/crewchief_loop.py` — find `process_tick()` and how it dispatches to events
  2. Read `backend/src/intelligence/event_engine.py:24-40` — `EventEngine.__init__` and event registration
  3. Run a minimal repro: instantiate `CrewChiefRuntime` with a recording audio_player, inject a `TelemetryFrame` with low fuel, check if any event fires
  4. Check the `should_suppress` path in `backend/src/intelligence/base_event.py:52-57` — does it return True unconditionally?
  5. Check the `applicable` path: does the event class filter by session type/phase that the test frame doesn't satisfy?
  6. Check `_enabled()` path: `global_settings.message_type_enabled(self.category)` — is `global_settings` a singleton that's not initialized in tests?
  7. Identify the EARLIEST gate that returns False, preventing the event from firing
  8. Document findings

  **Must NOT do**:
  - Do NOT modify event business logic (per plan guardrail)
  - Do NOT add test-only bypasses (the fix should work in production too)
  - Do NOT skip the investigation (proper-fix mandate)

  **Recommended Agent Profile**:
  - **Category**: `deep` — multi-file trace, root cause analysis
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T1, T5)
  - **Parallel Group**: Wave 1
  - **Blocked By**: None (can start in parallel with T1)

  **References**:
  - `backend/src/services/crewchief_loop.py` — main entry
  - `backend/src/intelligence/event_engine.py:24-40` — event dispatch
  - `backend/src/intelligence/base_event.py:52-57` — should_suppress
  - `backend/src/intelligence/base_event.py:49-50` — applicable
  - `backend/src/intelligence/base_event.py:59-61` — _enabled
  - `docs/pipeline-review/evidence/pipeline-review/task-7-crewchief-events.txt`

  **Acceptance Criteria**:
  - [ ] Exact gate identified (file:line)
  - [ ] Why the gate returns False for injected frames documented
  - [ ] Production impact: does this gate also fail in real LMU race? If yes, this is a critical production bug
  - [ ] Recommendation: how to fix (specific to the gate, not shotgun)

  **Evidence**: `.omo/notepads/fix-crewchief-pipeline/learnings.md` (T3 section)

---

- [ ] 4. Fix CrewChiefRuntime so 12 events fire on injected TelemetryFrame

  **What to do**:
  1. Based on Task 3's root cause, implement the specific fix
  2. Most likely candidates (in order of probability):
     - a) `global_settings` singleton not initialized in test → fix by ensuring it loads defaults if not configured
     - b) `should_suppress` returns True for test frames because `event_flags.on_manual_formation_lap` is unset → fix by using `getattr(event_flags, 'on_manual_formation_lap', False)` or similar
     - c) `applicable()` filters by session_phase that test frame doesn't set → fix by adding more permissive defaults
     - d) TelemetryFrame field name mismatch (e.g., `fuel_laps_left` vs expected field) → fix by aligning names
  3. Whichever it is, the fix should be MINIMAL and address the root cause
  4. Verify: `cd backend && pytest tests/test_crewchief_event_flow_e2e.py -v --tb=short 2>&1 | tail -20`
  5. Verify: `cd backend && pytest tests/test_crewchief_pipeline.py tests/test_crewchief_integration.py -q 2>&1 | tail -5` (no regression in pre-existing tests)
  6. Verify: full Phase 1 E2E suite — `cd backend && pytest tests/test_crewchief_event_flow_e2e.py tests/test_spotter_flow_e2e.py tests/test_strategy_flow_e2e.py tests/test_frame_cache_flow_e2e.py -q 2>&1 | tail -5`

  **Must NOT do**:
  - Do NOT modify event trigger logic in `backend/src/intelligence/events/*.py` (per plan guardrail, unless the investigation proves the event class is the problem)
  - Do NOT add shotgun fixes (one per gate, fix only the actual broken one)
  - Do NOT add `force=True` parameters that bypass validation

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — careful code change, multiple test verifications
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on T3)
  - **Blocked By**: 3

  **References**:
  - Task 3's findings
  - `docs/pipeline-review/BUGS.md` (Bug #1)

  **Acceptance Criteria**:
  - [ ] `test_crewchief_event_flow_e2e.py` passes 12/12
  - [ ] Pre-existing tests don't regress
  - [ ] Spotter and strategy E2E tests still pass
  - [ ] Fix is minimal (≤10 lines changed)

  **Commit**: YES
  - Message: `fix(crewchief): root cause for events not firing from injected TelemetryFrame`
  - Files: depends on root cause (likely `crewchief_loop.py` or `event_engine.py`)

  **Evidence**: `.omo/notepads/fix-crewchief-pipeline/learnings.md` (T4 section)

---

## WAVE 3: Bug 4 — UI Renderer for crewchief alerts

- [ ] 5. Design RadioOverlay changes to render crewchief.events

  **What to do**:
  1. Read `frontend/src/components/RadioOverlay.tsx:1-50` — current rendering
  2. Read `frontend/src/store/config.ts` — `crewchief` state shape (events, latestByCategory)
  3. Design the rendering:
     - How alerts appear (overlay? sidebar? tooltip?)
     - Severity styling (low/medium=neutral, high=yellow, critical=red)
     - Auto-removal (8s for low/medium, persistent for high/critical)
     - Data-testid for E2E tests
  4. Write the design in `.omo/notepads/fix-crewchief-pipeline/learnings.md` (T5 section)
  5. Identify if a NEW component is needed or if RadioOverlay can be extended
  6. List the exact file(s) to modify

  **Must NOT do**:
  - Do NOT implement yet (just design)
  - Do NOT change the store schema (work with what's there)
  - Do NOT add new dependencies (CSS-in-JS, etc.)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low` — read + design + document
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T1, T3)
  - **Parallel Group**: Wave 1
  - **Blocked By**: None

  **References**:
  - `frontend/src/components/RadioOverlay.tsx`
  - `frontend/src/store/config.ts:71-142`
  - `docs/pipeline-review/evidence/pipeline-review/task-14-crewchief-visual.txt`
  - `docs/pipeline-review/TEST-INVENTORY.md` (T14 section)

  **Acceptance Criteria**:
  - [ ] Design written in notepad
  - [ ] File(s) to modify identified
  - [ ] Data-testid chosen (for E2E assertions)
  - [ ] Severity styling approach decided

  **Evidence**: `.omo/notepads/fix-crewchief-pipeline/learnings.md` (T5 section)

---

- [ ] 6. Implement UI renderer + verify DOM assertions

  **What to do**:
  1. Based on Task 5's design, implement the renderer
  2. Use React + Tailwind (already in stack) — no new deps
  3. Follow existing patterns in `frontend/src/components/` (e.g., how `RadioOverlay` already renders other alerts)
  4. Add `data-testid` attributes for the 3 severity levels
  5. Implement auto-removal with `setTimeout` for low/medium (8s per the schema)
  6. Update the existing Playwright test `frontend/e2e/crewchief-visual.spec.ts` — promote the soft DOM checks to hard `expect(locator).toBeVisible()` assertions
  7. Verify: `cd frontend && npx tsc --noEmit` → 0 errors
  8. Verify: `cd frontend && npx vitest run 2>&1 | tail -5` → 88/88 still pass
  9. Verify: `cd frontend && npx playwright test e2e/crewchief-visual.spec.ts --reporter=list 2>&1 | tail -10` → 3/3 pass with hard DOM assertions

  **Must NOT do**:
  - Do NOT add `as any` or `@ts-ignore`
  - Do NOT add new npm dependencies
  - Do NOT modify the store schema (read existing `crewchief.events` shape)
  - Do NOT add audio/notification logic (that's a separate concern)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — React + Tailwind + Playwright test update
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on T5)
  - **Blocked By**: 5

  **References**:
  - Task 5's design
  - `frontend/src/components/RadioOverlay.tsx` (pattern to follow)
  - `frontend/e2e/crewchief-visual.spec.ts` (test to update)
  - `docs/pipeline-review/TEST-STRATEGY.md`

  **Acceptance Criteria**:
  - [ ] Alerts visible in DOM (not just store)
  - [ ] Severity styling applied (low/medium=neutral, high=yellow, critical=red)
  - [ ] Auto-removal works for low/medium
  - [ ] High/critical persist
  - [ ] Playwright test promotes soft → hard DOM assertions, 3/3 pass
  - [ ] tsc 0 errors
  - [ ] vitest 88/88 still pass

  **Commit**: YES
  - Message: `feat(frontend): render CrewChief alerts in RadioOverlay`
  - Files: depends on design (likely `RadioOverlay.tsx` + updated `crewchief-visual.spec.ts`)

  **Evidence**: `.omo/notepads/fix-crewchief-pipeline/learnings.md` (T6 section)

---

## Final Verification Wave (MANDATORY)

> 4 review agents run in PARALLEL after all 3 bugs are fixed.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Verify: 3 commits on `feature/benchmark-llm`, 3 bugs fixed, all 12+8+3 tests pass, no scope creep.
  Output: `Bugs [3/3] | Tests [23/23] | Commits [3/3] | Evidence [N files] | VERDICT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run: `pytest backend/tests/test_crewchief_event_flow_e2e.py backend/tests/test_frame_cache_flow_e2e.py` + `cd frontend && npx vitest run && npx tsc --noEmit`. Check anti-patterns.
  Output: `Build | Lint | Tests | Files | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Execute all 3 E2E test files. Cross-workflow: inject frame → event fires → WS broadcast → store update → DOM render. Edge case: empty frame, invalid category, rapid succession.
  Output: `Tests [N/N] | Integration [N/N] | Edge Cases [N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  Verify: each task did what it claimed, no empty passes, no mocking abuse, no new deps. Event business logic not modified beyond root cause.
  Output: `Tests [N/N honest] | Mocking [clean] | Scope [contained] | VERDICT`

---

## Commit Strategy

- **Wave 1 (Bug 2)**: `fix(frame_cache): proper dedup — skip reader when elapsed_time unchanged` — 1 file
- **Wave 2 (Bug 1)**: `fix(crewchief): root cause for events not firing from injected TelemetryFrame` — 1-2 files
- **Wave 3 (Bug 4)**: `feat(frontend): render CrewChief alerts in RadioOverlay` — 1 file

---

## Success Criteria

### Verification Commands
```bash
# After Wave 1
cd backend && pytest tests/test_frame_cache_flow_e2e.py -v --tb=short 2>&1 | tail -10

# After Wave 2
cd backend && pytest tests/test_crewchief_event_flow_e2e.py -v --tb=short 2>&1 | tail -15

# After Wave 3
cd frontend && npx playwright test e2e/crewchief-visual.spec.ts --reporter=list 2>&1 | tail -10

# Full verification (Final Wave)
cd backend && pytest tests/test_crewchief_event_flow_e2e.py tests/test_frame_cache_flow_e2e.py -v
cd frontend && npx vitest run && npx tsc --noEmit && npx playwright test --reporter=list
```

### Final Checklist
- [ ] Bug 2 fixed: FrameCache dedup is real (reader called once on same et)
- [ ] Bug 1 fixed: 12/12 CrewChief events fire on injected TelemetryFrame
- [ ] Bug 4 fixed: CrewChief alerts visible in DOM with severity styling
- [ ] All F1-F4 APPROVED
- [ ] 3 commits on `feature/benchmark-llm` (one per bug)
- [ ] No new dependencies added
