# Pipeline Review Documentation

**Purpose:** Reference documentation for the test review of the Vantare Ingeniero IA pipeline. The review replaced mock-heavy unit tests with end-to-end tests that use real components, real WebSockets, real dataclasses, and behavior assertions. It surfaced real bugs in the production code path and real contract drift between the test suite and the implementation.

This index links to the eight docs in this folder. Each doc is self-contained and can be read independently.

---

## Executive Summary

The review ran in five waves (Phase 0 through Phase 4) on branch `feature/benchmark-llm`. Phase 0 fixed 5 API drift issues in the pre-existing crewchief tests (commit `c295dcc`). Phase 1 added 5 backend E2E test files (76 of 89 tests pass; the 13 failures are real production findings, not test bugs). Phase 2 added a multi-client WebSocket test (1 of 12 tests passes; 11 failures point to a real WebSocket receive pattern incompatibility with starlette). Phase 3 added 4 Playwright E2E specs (6 of 6 tests pass; 3 of them carry soft findings about a missing DOM renderer for crewchief alerts). Phase 4 stack-dev smoke was deferred because the LLM server is down and PTT is excluded from the scope.

The headline result: the test suite now catches real bugs. `TestDedupIsReal::test_same_elapsed_time_reader_called_once` proves the FrameCache dedup is half-real. `TestThreeClientsAllReceive::test_three_clients_get_identical_broadcast` proves the WebSocket broadcast pattern is fragile. `TestCrewChiefEventFlowE2E` proves the crewchief runtime does not emit alerts for injected TelemetryFrames when the lifespan starts the way production does. The Phase 3 soft finding proves no React component currently renders `crewchief.events` even though the store, the WebSocket pipeline, and the Zustand action chain all work correctly.

The LLM migration is out of scope for this review. When the new LLM server arrives (specific API, personal subscription, exposed through clients not directly from the backend), the PTT workflow, `backend/src/intelligence/llm_client.py`, and several `.env` keys will all need to change. See `LLM-MIGRATION.md` for the impact summary and the migration checklist.

---

## Findings at a Glance

| Severity | Count | Examples |
|----------|-------|----------|
| Real production bug (HIGH) | 1 | WS receive pattern incompatible with starlette (`test_ws_multi_client_e2e.py` — 11/12 fail) |
| Real production bug (MEDIUM) | 2 | FrameCache dedup calls reader on every call (`frame_cache.py:15-19`); no React component renders crewchief alerts |
| Real production bug (LOW) | 2 | CrewChiefRuntime lifespan uses wrong kwarg for 9 of 12 events; test pollution in `test_pipeline_deterministic` |
| API drift (Phase 0 — already fixed) | 5 | `audio_player` kwarg, `reset_all` alias, `max_rpm`/`num_pitstops` fields, FakeAudioPlayer message lists |
| API drift (documented, not fixed) | 21 | Pre-existing tests that still fail after Phase 0 (categorized A/B/C/D/E) |

---

## Docs in This Folder

1. **[README.md](README.md)** — this file (index, executive summary, findings table)
2. **[BUGS.md](BUGS.md)** — catalog of all 5 real production bugs and the 21 documented API drift issues
3. **[TEST-STRATEGY.md](TEST-STRATEGY.md)** — the testing philosophy: real components over mocks, when mocks are acceptable, the "real WS, real dataclasses, real assertions" principle
4. **[TEST-INVENTORY.md](TEST-INVENTORY.md)** — full catalog of every test file (Phase 0, Phase 1, Phase 3), with purpose, scope, what each catches, and how to maintain it
5. **[MAINTENANCE.md](MAINTENANCE.md)** — how to add a new E2E test, when to use real components vs fakes, what NOT to mock, CI gate suggestions
6. **[LLM-MIGRATION.md](LLM-MIGRATION.md)** — the upcoming LLM server replacement: current state, new architecture, impact on code and tests, migration checklist
7. **[ARCHITECTURE.md](ARCHITECTURE.md)** — pipeline architecture after the review with a data flow diagram and performance notes
8. **[FIX-PLANS-SUMMARY.md](FIX-PLANS-SUMMARY.md)** — overview of the three fix plans that will resolve the 5 real bugs

---

## Source of Truth

These docs are derived from:

- The plan: `.omo/plans/pipeline-review.md` (1158 lines, 5 phases)
- The evidence: `.omo/evidence/pipeline-review/task-*.txt` (21 evidence files: pytest output, console logs, per-test text summaries, screenshots)
- The learnings: `.omo/notepads/pipeline-review/learnings.md` (subagent discoveries and gotchas)
- The new test files: `backend/tests/test_*_e2e.py` (Phase 1) and `frontend/e2e/*.spec.ts` (Phase 3)
- The key source files: `backend/src/services/frame_cache.py`, `crewchief_loop.py`, `event_bridge.py`; `frontend/src/hooks/useWebSocket.ts`, `store/config.ts`

All file paths and line numbers in these docs reference real files in the working tree. No paths or numbers are fabricated.

---

## Branch and Commits

Active branch: `feature/benchmark-llm`

The three commits that produced the test review:

```
6ac49b7  test(frontend): Phase 3 Playwright E2E for 4 critical user paths
4486362  test(e2e): Phase 1 backend E2E workflow tests for 4 critical paths
c295dcc  fix(events): Phase 0 API drift fixes for pre-existing crewchief tests
```

The `agents.md` and `AGENTS.md` files at the repo root, plus the `backend/AGENTS.md` and `frontend/AGENTS.md` per-package files, were not modified by the review. They are the source of truth for repo-wide conventions and command references.

---

## How to Read These Docs

If you are a developer working on a bug fix, start with `BUGS.md` and `FIX-PLANS-SUMMARY.md`. If you are adding a new test, read `TEST-STRATEGY.md` and `MAINTENANCE.md`. If you are onboarding or trying to understand the system shape, read `ARCHITECTURE.md` and `TEST-INVENTORY.md`. If you are planning the LLM migration, read `LLM-MIGRATION.md`. The docs cross-link where relevant, so you can navigate from any one to the others without backtracking.
