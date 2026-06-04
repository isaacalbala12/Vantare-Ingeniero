# Fix Plan 3: Test Hygiene

## TL;DR

> **Quick Summary**: Fix test pollution in `test_pipeline_deterministic`, add 6 missing API aliases/fields to source code (Categories A/B/C from BUGS.md), remove unauthorized npm dependencies, and clean up `@ts-ignore` instances. This resolves Bug 5 and gets 18+ of the 21 documented API drift failures passing, achieving the 22/22 pre-existing tests goal.
> 
> **Deliverables**:
> - Bug 5 fixed: `test_pipeline_deterministic` passes in full suite (no test pollution)
> - Category A fixed: `play_message`, `play_message_immediately`, `is_applicable` aliases on `AbstractEvent`
> - Category B fixed: `is_pitting_this_lap`, `waiting_for_driver_is_ok_response` fields on `EventFlags`
> - Category C fixed: `weather`, `track_definition`, `overheating` fields on GameStateData subclasses
> - npm deps cleaned: `@testing-library/react`, `happy-dom` removed from `frontend/package.json`
> - `@ts-ignore` audit: no new instances in source (e2e/ specs are exempt)
> 
> **Estimated Effort**: Short (4-6 tasks, mainly one-liners + fixture change)
> **Parallel Execution**: YES — 2 waves
> **Critical Path**: Category A → Category B → Category C (declarations must exist before tests reference them)

---

## Context

### Original Request
The pipeline-review completed with 3 fix plans identified. Plan 3 covers Bug 5 (test pollution) and the 21 documented API drift issues from the pre-existing test suite (Categories A-E). 18 of the 21 are mechanical one-liner fixes; 3 need deeper investigation (Categories D+E, deferred here).

### Interview Summary
**Key Discussions**:
- Fix aggression: proper-fix (root cause) for all bugs, no quick patches
- 22/22 pre-existing tests goal — Plan 3 targets 18 of the 21 remaining failures; the 3 Category D/E failures are explicitly deferred
- Unauthorized npm deps found by F4 audit: `@testing-library/react` and `happy-dom` (pre-existing, not from pipeline-review)
- `~30 @ts-ignore` / `(window as any)` instances in E2E specs — these are documented and allowed; Plan 3 audits for new instances only

### Metis Review
**Identified Gaps** (addressed):
- Gap: No explicit test for Category D/E — fixed by making deferral explicit with documented rationale
- Gap: Risk of `@ts-ignore` audit being too broad — narrowed to source files only (not e2e/ specs)

---

## Work Objectives

### Core Objective
Fix all mechanical API drift issues in the pre-existing test suite, eliminate test pollution, and clean up unauthorized dependencies so the full test suite (22 pre-existing + 5 E2E files + 4 Playwright specs) is green and trustworthy.

### Concrete Deliverables
- `backend/src/intelligence/base_event.py` — 3 new aliases (`play_message`, `play_message_immediately`, `is_applicable`)
- `backend/src/intelligence/event_flags.py` — 2 new fields (`is_pitting_this_lap`, `waiting_for_driver_is_ok_response`)
- `backend/src/models/game_state_data.py` — 3 new fields (`weather` on GSD, `track_definition` on SessionData, `overheating` on EngineData)
- `backend/tests/test_pipeline_deterministic.py` — fixture to reset singletons (fixes Bug 5)
- `frontend/package.json` — remove `@testing-library/react` and `happy-dom`
- No new `@ts-ignore` in frontend source files

### Definition of Done
- [ ] `pytest tests/ -v` — 18 additional tests pass (Category A/B/C fixed)
- [ ] `pytest tests/test_pipeline_deterministic.py -v` alone AND in full suite — both pass
- [ ] `cd frontend && npx tsc --noEmit` — passes (no new @ts-ignore)
- [ ] `grep @ts-ignore frontend/src/ --include="*.ts" --include="*.tsx" -r` — same count as pre-review baseline
- [ ] `grep -E "@testing-library/react|happy-dom" frontend/package.json` — not found

### Must Have
- All 6 API additions (Categories A/B/C) must be backward-compatible — no renames, no removals
- Test pollution fix must use a fixture, not test ordering hacks
- npm dep removal must not break existing frontend tests

### Must NOT Have (Guardrails)
- NO changes to event business logic in `backend/src/intelligence/events/`
- NO new pip/npm dependencies
- NO test ordering or `@pytest.mark.order` hacks for the pollution fix
- NO removal of `@ts-ignore` in `frontend/e2e/` (specs are allowed to use it)
- NO attempt to fix Category D or E logic-level issues in this plan

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest + vitest + Playwright)
- **Automated tests**: Tests-after (existing tests verify the fixes)
- **Framework**: pytest (backend) + vitest (frontend) + Playwright (e2e)

### QA Policy
Every task MUST include agent-executed QA scenarios. Evidence saved to `.omo/evidence/fix-test-hygiene/task-{N}-{scenario}.{ext}`.

---

## Execution Strategy

### Parallel Execution Waves
```
Wave 1 (Start Immediately — 4 independent API fixes + test pollution):
├── Task 1: Category A — Add 3 aliases to AbstractEvent [quick]
├── Task 2: Category B — Add 2 fields to EventFlags [quick]
├── Task 3: Category C — Add 3 fields to GameStateData models [quick]
├── Task 4: Bug 5 — Fix test pollution in test_pipeline_deterministic [quick]
└── Task 5: npm/@ts-ignore cleanup [quick]

Wave 2 (After ALL tasks — verify the full suite):
├── Task 6: Integration verification — run full test suite [unspecified-high]
```

---

## TODOs

- [ ] 1. Category A — Add method aliases to `AbstractEvent`

  **What to do**:
  - Open `backend/src/intelligence/base_event.py`
  - Find the `AbstractEvent` class
  - Add three aliases after the existing `play()` and `play_imm()` methods:
    ```python
    play_message = play
    play_message_immediately = play_imm
    is_applicable = applicable
    ```
  - These are pure aliases — no logic changes, no new behavior

  **Must NOT do**:
  - Do NOT rename `play()`, `play_imm()`, or `applicable()` — keep the originals
  - Do NOT add type annotations that differ from the originals

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Trivial one-liner aliases in a single file
  - **Skills**: None needed (simple Python attribute assignment)
  - **Skills Evaluated but Omitted**: All — no specialized skills required

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4, 5)
  - **Blocks**: Task 6 (integration verification)
  - **Blocked By**: None (can start immediately)

  **References**:
  - `backend/src/intelligence/base_event.py` — AbstractEvent class with `play()`, `play_imm()`, `applicable()` methods (the originals these aliases point to)
  - `backend/tests/test_crewchief_event_flow_e2e.py:92-99` — runtime monkey-patch that proves these aliases work (already tested at runtime)

  **Acceptance Criteria**:
  - [ ] Python import test: `python -c "from backend.src.intelligence.base_event import AbstractEvent; e = AbstractEvent.__new__(AbstractEvent); assert e.play_message == e.play; assert e.play_message_immediately == e.play_imm; assert e.is_applicable == e.applicable"`
  - [ ] The 6 pre-existing tests from Category A now pass (they call these methods directly)

  **QA Scenarios**:

  ```
  Scenario: Verify aliases resolve correctly at runtime
    Tool: Bash (python -c)
    Preconditions: base_event.py edited with aliases
    Steps:
      1. python -c "from backend.src.intelligence.base_event import AbstractEvent; e = AbstractEvent.__new__(AbstractEvent); print('play' if e.play_message == e.play else 'FAIL'); print('play_imm' if e.play_message_immediately == e.play_imm else 'FAIL'); print('applicable' if e.is_applicable == e.applicable else 'FAIL')"
    Expected Result: Prints "play", "play_imm", "applicable" (3 lines)
    Failure Indicators: Any line prints "FAIL"
    Evidence: .omo/evidence/fix-test-hygiene/task-1-aliases.txt

  Scenario: No AttributeError when tests call the aliases
    Tool: Bash (pytest)
    Preconditions: base_event.py edited with aliases
    Steps:
      1. pytest tests/test_tyre_monitor.py -v --no-header -x -q 2>&1 | tail -20
    Expected Result: No AttributeError about `play_message` or `play_message_immediately`
    Failure Indicators: pytest exits with error mentioning missing attribute
    Evidence: .omo/evidence/fix-test-hygiene/task-1-tyre-monitor.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/fix-test-hygiene/task-1-aliases.txt` — alias resolution output
  - [ ] `.omo/evidence/fix-test-hygiene/task-1-tyre-monitor.txt` — Category A test result

  **Commit**: YES (groups with Tasks 2, 3, 4)
  - Message: `fix(events): lift API drift aliases into source (Categories A, B, C)`
  - Files: `backend/src/intelligence/base_event.py`, `backend/src/intelligence/event_flags.py`, `backend/src/models/game_state_data.py`, `backend/tests/test_pipeline_deterministic.py`
  - Pre-commit: `pytest tests/test_tyre_monitor.py tests/test_battery.py tests/test_frozen_order_monitor.py tests/test_pit_stops.py -v --no-header -q 2>&1 | tail -5`

---

- [ ] 2. Category B — Add missing fields to `EventFlags`

  **What to do**:
  - Open `backend/src/intelligence/event_flags.py`
  - Find the `EventFlags` class dataclass
  - Add two new boolean fields with defaults:
    ```python
    is_pitting_this_lap: bool = False
    waiting_for_driver_is_ok_response: bool = False
    ```
  - These fields are already referenced by event files (`fuel.py:48`, `damage_reporting.py:72`)
  - They should be adjacent to the existing `is_pitting` and `waiting_driver_ok` fields for consistency

  **Must NOT do**:
  - Do NOT rename existing fields (`is_pitting`, `waiting_driver_ok`)
  - Do NOT change any existing field defaults

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Two field additions in a dataclass — no logic
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4, 5)
  - **Blocks**: Task 6
  - **Blocked By**: None

  **References**:
  - `backend/src/intelligence/event_flags.py` — existing `EventFlags` dataclass with fields like `is_pitting`, `waiting_driver_ok`
  - `backend/src/intelligence/events/fuel.py:48` — reads `event_flags.is_pitting_this_lap`
  - `backend/src/intelligence/events/damage_reporting.py:72` — reads `event_flags.waiting_for_driver_is_ok_response`
  - `backend/tests/test_crewchief_event_flow_e2e.py:107-111` — runtime setattr that proves these fields work

  **Acceptance Criteria**:
  - [ ] Python import test: `python -c "from backend.src.intelligence.event_flags import EventFlags; f=EventFlags(); assert f.is_pitting_this_lap == False; assert f.waiting_for_driver_is_ok_response == False"`
  - [ ] The 4 pre-existing tests from Category B now pass (they reference these fields)

  **QA Scenarios**:

  ```
  Scenario: Verify new fields exist with correct defaults
    Tool: Bash (python -c)
    Preconditions: event_flags.py edited
    Steps:
      1. python -c "from backend.src.intelligence.event_flags import EventFlags; f=EventFlags(); print('OK' if f.is_pitting_this_lap==False and f.waiting_for_driver_is_ok_response==False else 'FAIL')"
    Expected Result: Prints "OK"
    Failure Indicators: Prints "FAIL" or raises AttributeError
    Evidence: .omo/evidence/fix-test-hygiene/task-2-flags.txt

  Scenario: Existing event files can access the new fields
    Tool: Bash (python -c)
    Preconditions: event_flags.py edited
    Steps:
      1. python -c "from backend.src.intelligence.event_flags import EventFlags; from backend.src.intelligence.events.fuel import FuelMonitor; f=EventFlags(); m=FuelMonitor.__new__(FuelMonitor); print('OK')"
    Expected Result: Prints "OK"
    Failure Indicators: ImportError or AttributeError
    Evidence: .omo/evidence/fix-test-hygiene/task-2-fuel-import.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/fix-test-hygiene/task-2-flags.txt`
  - [ ] `.omo/evidence/fix-test-hygiene/task-2-fuel-import.txt`

  **Commit**: YES (groups with Tasks 1, 3, 4)
  - Message: `fix(events): lift API drift aliases into source (Categories A, B, C)`
  - Files: grouped with Task 1

---

- [ ] 3. Category C — Add missing fields to `GameStateData` models

  **What to do**:
  - Open `backend/src/models/game_state_data.py`
  - Find the three dataclass definitions and add one field each:
    1. `GameStateData` class: add `weather: Any = None`
    2. `SessionData` class: add `track_definition: Any = None`
    3. `EngineData` class: add `overheating: bool = False`
  - Ensure `Any` is imported from `typing` (it should already be)
  - Place fields in logical position (alphabetical or near related fields)

  **Must NOT do**:
  - Do NOT remove or rename any existing fields
  - Do NOT change field types — use `Any` for the two optional fields to match the existing pattern

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Three field additions across three subclasses — mechanical work
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4, 5)
  - **Blocks**: Task 6
  - **Blocked By**: None

  **References**:
  - `backend/src/models/game_state_data.py` — `GameStateData`, `SessionData`, `EngineData` dataclasses
  - `backend/src/intelligence/events/conditions_monitor.py` — references `gsd.weather`
  - `backend/src/intelligence/events/pit_stops.py` — references `session.track_definition`
  - `backend/src/intelligence/events/engine_monitor.py` — references `engine.overheating`
  - `backend/tests/test_crewchief_event_flow_e2e.py:407,424,431` — runtime setattr proving these fields work

  **Acceptance Criteria**:
  - [ ] Python import test: `python -c "from backend.src.models.game_state_data import GameStateData, SessionData, EngineData; g=GameStateData(); assert hasattr(g,'weather'); s=SessionData(); assert hasattr(s,'track_definition'); e=EngineData(); assert hasattr(e,'overheating')"`
  - [ ] The 8 pre-existing tests from Category C now pass

  **QA Scenarios**:

  ```
  Scenario: Verify new fields exist on model instances
    Tool: Bash (python -c)
    Preconditions: game_state_data.py edited
    Steps:
      1. python -c "from backend.src.models.game_state_data import *; g=GameStateData(); s=SessionData(); e=EngineData(); print('OK' if (hasattr(g,'weather') and hasattr(s,'track_definition') and hasattr(e,'overheating') and e.overheating==False) else 'FAIL')"
    Expected Result: Prints "OK"
    Failure Indicators: Prints "FAIL" or raises AttributeError
    Evidence: .omo/evidence/fix-test-hygiene/task-3-gsd-fields.txt

  Scenario: Event files can access the new fields without setattr
    Tool: Bash (python -c)
    Preconditions: game_state_data.py edited
    Steps:
      1. python -c "from backend.src.models.game_state_data import EngineData; e=EngineData(); e.overheating=True; print('OK' if e.overheating else 'FAIL')"
    Expected Result: Prints "OK"
    Failure Indicators: Prints "FAIL" or raises AttributeError
    Evidence: .omo/evidence/fix-test-hygiene/task-3-engine-overheat.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/fix-test-hygiene/task-3-gsd-fields.txt`
  - [ ] `.omo/evidence/fix-test-hygiene/task-3-engine-overheat.txt`

  **Commit**: YES (groups with Tasks 1, 2, 4)
  - Message: `fix(events): lift API drift aliases into source (Categories A, B, C)`
  - Files: grouped with Task 1

---

- [ ] 4. Bug 5 — Fix test pollution in `test_pipeline_deterministic`

  **What to do**:
  - Open `backend/tests/test_pipeline_deterministic.py`
  - Identify the shared singletons that cause pollution:
    - `event_flags` singleton (likely imported from `backend.src.intelligence.event_flags`)
    - `global_settings.messages` set
    - `_executor` thread pool on any shared `CrewChiefRuntime` instance
  - Add a `@pytest.fixture(autouse=True)` that resets these singletons before each test:
    ```python
    @pytest.fixture(autouse=True)
    def reset_singletons():
        """Reset shared state between tests to prevent pollution."""
        from backend.src.intelligence import event_flags
        # Re-instantiate event_flags to clear state
        event_flags.EventFlags.__init__(event_flags.event_flags)
        
        from backend.src.services.crewchief_loop import global_settings
        global_settings.messages.clear()
        
        yield  # test runs here
        
        # No cleanup needed after — fixture resets before each test
    ```
  - The exact reset code depends on how the singletons are structured. Read the file first and tailor the reset to match.
  - Alternative approach if the singletons are module-level instances: use `importlib.reload(module)` for the specific modules that hold state.

  **Must NOT do**:
  - Do NOT use `@pytest.mark.order` or `pytest-ordering` to work around pollution
  - Do NOT use `@pytest.fixture(scope="session")` — must reset per-test
  - Do NOT delete or modify other tests to hide the pollution
  - Do NOT use `importlib.reload()` on modules with C extensions or complex dependency chains

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single fixture addition + reading the test file to identify singletons
  - **Skills**: None needed beyond Python pytest knowledge

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 5)
  - **Blocks**: Task 6
  - **Blocked By**: None

  **References**:
  - `backend/tests/test_pipeline_deterministic.py` — the failing test (passes alone, fails in suite)
  - `backend/src/intelligence/event_flags.py` — `event_flags` singleton with mutable state
  - `backend/src/services/crewchief_loop.py` — `global_settings` with `messages` set
  - F2 verification report (`.omo/evidence/pipeline-review/task-f2.txt`) — flagged test pollution as one of 6 REJECT issues
  - `docs/pipeline-review/BUGS.md:117-131` — Bug 5 documentation

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_pipeline_deterministic.py -v` — passes when run alone (baseline: already passes)
  - [ ] `pytest tests/ -v -k "deterministic"` — passes when run after other tests in the suite
  - [ ] `pytest tests/test_pipeline_deterministic.py tests/test_frame_cache_flow_e2e.py -v` — both pass when run together (this was the failing pair in F2)

  **QA Scenarios**:

  ```
  Scenario: Test passes when run after pollution-inducing tests
    Tool: Bash (pytest)
    Preconditions: test_pipeline_deterministic.py fixture added
    Steps:
      1. pytest tests/test_frame_cache_flow_e2e.py -v --no-header -q 2>&1 | tail -3
      2. pytest tests/test_pipeline_deterministic.py -v --no-header -q 2>&1 | tail -5
    Expected Result: Both test runs report PASS
    Failure Indicators: Second run fails with state-leak error
    Evidence: .omo/evidence/fix-test-hygiene/task-4-pollution-fixed.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/fix-test-hygiene/task-4-pollution-fixed.txt`

  **Commit**: YES (groups with Tasks 1, 2, 3)
  - Message: `fix(events): lift API drift aliases into source (Categories A, B, C)`
  - Files: grouped with Task 1

---

- [ ] 5. Clean up unauthorized npm dependencies and audit `@ts-ignore`

  **What to do**:
  1. Open `frontend/package.json`
  2. Find and remove `@testing-library/react` from `devDependencies`
  3. Find and remove `happy-dom` from `devDependencies`
  4. Run `cd frontend && npm uninstall @testing-library/react happy-dom` to clean up `node_modules` and `package-lock.json`
  5. Run `grep -rn "@ts-ignore" frontend/src/ --include="*.ts" --include="*.tsx"` to establish the baseline count
  6. Compare against pre-review count (if known) or document the current count
  7. Run `cd frontend && npx tsc --noEmit` to verify no new type errors from the removals

  **Must NOT do**:
  - Do NOT remove `@testing-library/react` or `happy-dom` from `frontend/e2e/` — only from source
  - Do NOT modify or remove any other dependencies
  - Do NOT remove `vitest` or `playwright` (they are required)
  - Do NOT remove `@ts-ignore` from `frontend/e2e/*.spec.ts` — those are documented and allowed

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Package.json edit + npm command + grep audit
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 4)
  - **Blocks**: Task 6
  - **Blocked By**: None

  **References**:
  - `frontend/package.json` — npm dependencies
  - F4 audit findings from pipeline-review: `.omo/plans/pipeline-review.md:1106` — flagged 2 unauthorized deps
  - `docs/pipeline-review/BUGS.md` — F4 violations documented
  - `docs/pipeline-review/FIX-PLANS-SUMMARY.md:100-134` — Plan 3 scope includes "remove unauthorized @testing-library/react and happy-dom"

  **Acceptance Criteria**:
  - [ ] `grep -E "@testing-library/react|happy-dom" frontend/package.json` — not found
  - [ ] `cd frontend && npx tsc --noEmit` — passes (no type errors from dep removal)
  - [ ] `cd frontend && npx vitest run --reporter=verbose 2>&1 | tail -20` — passes (tests still work without these deps)
  - [ ] `grep -rn '@ts-ignore' frontend/src/ --include='*.ts' --include='*.tsx'` — count documented for baseline

  **QA Scenarios**:

  ```
  Scenario: Unauthorized deps removed
    Tool: Bash (grep)
    Preconditions: package.json edited, npm uninstall run
    Steps:
      1. grep -E "@testing-library/react|happy-dom" frontend/package.json
    Expected Result: No output (deps not found)
    Failure Indicators: grep finds matching lines
    Evidence: .omo/evidence/fix-test-hygiene/task-5-deps-cleaned.txt

  Scenario: Frontend tests still pass
    Tool: Bash (npx vitest)
    Preconditions: deps removed
    Steps:
      1. cd frontend && npx vitest run --reporter=verbose 2>&1
    Expected Result: All existing frontend tests pass
    Failure Indicators: Test failures related to missing @testing-library/react
    Evidence: .omo/evidence/fix-test-hygiene/task-5-vitest-pass.txt

  Scenario: TypeScript compiles without errors
    Tool: Bash (npx tsc)
    Preconditions: deps removed
    Steps:
      1. cd frontend && npx tsc --noEmit 2>&1
    Expected Result: No type errors (exit code 0)
    Failure Indicators: tsc reports errors
    Evidence: .omo/evidence/fix-test-hygiene/task-5-tsc-pass.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/fix-test-hygiene/task-5-deps-cleaned.txt`
  - [ ] `.omo/evidence/fix-test-hygiene/task-5-vitest-pass.txt`
  - [ ] `.omo/evidence/fix-test-hygiene/task-5-tsc-pass.txt`

  **Commit**: YES (separate commit)
  - Message: `chore(deps): remove unauthorized @testing-library/react and happy-dom`
  - Files: `frontend/package.json`, `frontend/package-lock.json` (and any test files that imported these)
  - Pre-commit: `cd frontend && npx vitest run --reporter=verbose 2>&1 | tail -5`

---

- [ ] 6. Integration verification — run full test suite

  **What to do**:
  1. Run the full backend test suite: `cd backend && pytest tests/ -v --no-header -q 2>&1`
  2. Count how many of the 18 targeted API drift failures (Categories A/B/C) now pass
  3. Count how many pre-existing tests now pass total (baseline was 22 pre-existing; Phase 0 fixed 5; target is 22+ more)
  4. Run the frontend test suite: `cd frontend && npx vitest run --reporter=verbose 2>&1`
  5. Run the TypeScript check: `cd frontend && npx tsc --noEmit 2>&1`
  6. Run the Playwright specs: `cd frontend && npx playwright test --reporter=line 2>&1`
  7. Document the final pass/fail counts and any remaining Category D/E failures (explicitly deferred)

  **Must NOT do**:
  - Do NOT attempt to fix Category D or E failures in this plan
  - Do NOT modify any test files except `test_pipeline_deterministic.py` (already done in Task 4)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Running and interpreting multiple test suites
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on all prior tasks)
  - **Parallel Group**: Wave 2 (final — single task)
  - **Blocks**: None (final verification)
  - **Blocked By**: Tasks 1, 2, 3, 4, 5

  **References**:
  - All files modified in Tasks 1-5
  - `docs/pipeline-review/BUGS.md` — for the before/after comparison
  - `docs/pipeline-review/TEST-INVENTORY.md` — for the expected pass counts

  **Acceptance Criteria**:
  - [ ] Category A: 6 pre-existing tests now pass (was 6 failing)
  - [ ] Category B: 4 pre-existing tests now pass (was 4 failing)
  - [ ] Category C: 8 pre-existing tests now pass (was 8 failing)
  - [ ] Bug 5: `test_pipeline_deterministic` passes both alone and in suite
  - [ ] Frontend: vitest passes, tsc passes, Playwright passes
  - [ ] Remaining failures: only Category D (2 logic-level) and Category E (1 test-infra) — explicitly documented as deferred

  **QA Scenarios**:

  ```
  Scenario: Full backend suite report
    Tool: Bash (pytest)
    Preconditions: All Tasks 1-5 complete
    Steps:
      1. cd backend && pytest tests/ -v --no-header -q 2>&1 | tail -30
    Expected Result: Output shows pass count increase from baseline + remaining known failures
    Failure Indicators: New failures from Category A/B/C tests that should now pass
    Evidence: .omo/evidence/fix-test-hygiene/task-6-full-suite.txt

  Scenario: Full frontend suite report
    Tool: Bash (vitest + tsc + playwright)
    Preconditions: All Tasks 1-5 complete
    Steps:
      1. cd frontend && npx vitest run --reporter=verbose 2>&1 | tail -20
      2. cd frontend && npx tsc --noEmit 2>&1 | tail -10
      3. cd frontend && npx playwright test --reporter=line 2>&1 | tail -20
    Expected Result: All three commands report PASS
    Failure Indicators: Any command reports FAIL
    Evidence: .omo/evidence/fix-test-hygiene/task-6-frontend-pass.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/fix-test-hygiene/task-6-full-suite.txt`
  - [ ] `.omo/evidence/fix-test-hygiene/task-6-frontend-pass.txt`

  **Commit**: NO (verification only, no code changes)
  - Note: If the verification reveals any issues, fix them before claiming completion. Do not commit broken state.

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read `.omo/plans/fix-test-hygiene.md` end to end. Verify each task's acceptance criteria was met. Check that no unauthorized changes were made (no event business logic changes, no new deps). Verify that Category D/E failures are explicitly deferred and not attempted.
  Output: `Tasks [N/N] | Must NOT Have [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Suite Verification** — `unspecified-high`
  Run `cd backend && pytest tests/ -v --no-header -q 2>&1`. Report before/after pass counts. Verify Category A/B/C failures are resolved. Verify `test_pipeline_deterministic` passes reliably.
  Output: `Before [22 pre-existing] | After [N passing] | Category A [6/6] | Category B [4/4] | Category C [8/8] | Bug 5 [PASS] | VERDICT`

- [ ] F3. **npm/tsc Audit** — `quick`
  Verify `grep -E "@testing-library/react|happy-dom" frontend/package.json` returns nothing. Verify `cd frontend && npx tsc --noEmit` passes. Verify `grep -rn '@ts-ignore' frontend/src/` count is documented.
  Output: `Deps [CLEAN] | tsc [PASS] | ts-ignore [BASELINE: N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read the "What to do", then `git diff` the changed files. Verify nothing beyond the plan was modified. Verify Category D/E files are untouched. Verify no event business logic was changed.
  Output: `Tasks [N/N compliant] | Scope Creep [CLEAN] | Event Logic [UNTOUCHED] | VERDICT`

---

## Commit Strategy

```
fix(events): lift API drift aliases into source (Categories A, B, C)
  - backend/src/intelligence/base_event.py
  - backend/src/intelligence/event_flags.py
  - backend/src/models/game_state_data.py
  - backend/tests/test_pipeline_deterministic.py

chore(deps): remove unauthorized @testing-library/react and happy-dom
  - frontend/package.json
  - frontend/package-lock.json
```

---

## Success Criteria

### Verification Commands
```bash
cd backend && pytest tests/ -v --no-header -q 2>&1 | tail -10
# Expected: Category A (6), B (4), C (8) — all passing; only Category D/E remain

cd frontend && npx vitest run --reporter=verbose 2>&1 | tail -5
# Expected: all tests pass

cd frontend && npx tsc --noEmit 2>&1
# Expected: exit code 0, no type errors

cd frontend && npx playwright test --reporter=line 2>&1 | tail -10
# Expected: all specs pass

grep -E "@testing-library/react|happy-dom" frontend/package.json
# Expected: no output
```

### Final Checklist
- [ ] Category A aliases added (3 aliases: `play_message`, `play_message_immediately`, `is_applicable`)
- [ ] Category B flags added (2 fields: `is_pitting_this_lap`, `waiting_for_driver_is_ok_response`)
- [ ] Category C model fields added (3 fields: `weather`, `track_definition`, `overheating`)
- [ ] Bug 5 fixed (test pollution fixture)
- [ ] npm deps cleaned (@testing-library/react, happy-dom removed)
- [ ] @ts-ignore baseline documented
- [ ] Categories D/E explicitly deferred with rationale documented
- [ ] Full suite passes with only D/E as known remaining failures
