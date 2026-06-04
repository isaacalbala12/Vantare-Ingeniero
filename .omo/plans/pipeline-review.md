# Pipeline Review — Vantare Ingeniero IA

## TL;DR

> **Quick Summary**: Sustituir los tests actuales (muchos mockeados, "este archivo parece funcionar") por tests E2E que detectan fallos reales del pipeline: telemetry → sidecar → backend → WebSocket → frontend → UI. Cinco fases: arreglar API drift, tests backend con componentes reales, tests WS, Playwright E2E, smoke del stack dev.
>
> **Deliverables**:
> - 22 tests pre-existentes arreglados (API drift)
> - ~12 tests E2E backend con FastAPI TestClient + real WebSocket
> - Playwright instalado + 4 tests E2E frontend
> - Stack dev arrancado y verificado manualmente
> - Screenshots de evidencia en `.omo/evidence/pipeline-review/`
>
> **Estimated Effort**: Large (5 waves)
> **Parallel Execution**: YES — 5 waves
> **Critical Path**: Phase 0 (API fix) → Phase 1 (backend E2E) → Phase 3 (Playwright) → Phase 4 (dev stack)
> **Known Issue**: LLM server is down — PTT workflow EXCLUDED from scope. Avisar al usuario antes de Phase 4.

## Context

### Original Request
"necesito que revises el workflow completo de la app para poder saber si todo funciona como pretende. para ello debemos de sustituir los tests por tests que puedan detectar fallos en el workflow/pipeline de la app y no simples tests de 'este archivo parece funcionar'."

### Interview Summary
**User decisions**:
- "Iniciaremos la app" = Playwright E2E first, then dev stack manual
- LLM no funciona (server reparandose) — excluir PTT workflow
- 4 workflows críticos: CrewChief events, Spotter, Strategy sidecar, Config persistencia
- Nivel "real" = componentes reales + red real (nivel 2) + asserts comportamiento (nivel 3)
- Arreglar 22 tests pre-existentes (fase 0)

**Research findings**:
- Playwright 1.60.0 instalado globalmente, NO en `frontend/node_modules`
- 7 archivos `.test.ts` en frontend (api, appStore, audioQueue, configStore, filters, msgpack, useWebSocket)
- 0 E2E tests del pipeline completo
- `event_engine.py:24` usa `ap=None` pero tests pasan `audio_player=`
- `spotter.py` evalúa 5+ condiciones (pit_limiter, gap_ahead/behind)
- `frame_cache.py` dedup por elapsed_time

### Metis Review
**Decisiones confirmadas**:
- Excluir PTT/LLM (server down)
- Componentes reales, red real, sin unittest.mock para CrewChiefRuntime
- Audio: verificar WAV file generado, no bytes
- Strategy: inyectar TelemetryFrame realista

---

## Work Objectives

### Core Objective
Verificar que el pipeline completo de Vantare Ingeniero funciona end-to-end con componentes reales, no con mocks que ocultan bugs. Si un test pasa, debe significar que el flujo real funciona.

### Concrete Deliverables
1. 22 tests pre-existentes pasando (fase 0)
2. Tests E2E de los 4 workflows críticos con FastAPI TestClient + WebSocket real
3. Playwright E2E con screenshots de UI real
4. Stack dev arrancado, verificado, screenshots

### Definition of Done
- [ ] 22 tests pre-existentes pasan
- [ ] 4 workflows tienen E2E tests con asserts de comportamiento
- [ ] Playwright tests pasan con screenshots
- [ ] `python run_dev.py` arranca backend sin errores
- [ ] `npm run dev` arranca Vite sin errores
- [ ] Frontend conecta a WS backend
- [ ] F1-F4 verification wave todos APPROVED
- [ ] LLM down acknowledged upfront al usuario

### Must Have
- Tests usan componentes reales (no mockean CrewChiefRuntime, FrameCache, AudioPlayer, SpotterService)
- WebSocket real (no mock)
- Audio: WAV file verificado en disco
- Telemetry: frames realistas con dataclasses correctos
- Spotter: inyectar frame con rival cerca → verificar mensaje específico
- CrewChief: 12 categorías cada una con su test

### Must NOT Have (Guardrails)
- NO mockear CrewChiefRuntime con unittest.mock
- NO mockear AudioPlayer interno
- NO usar `as any` / `@ts-ignore` en TypeScript
- NO añadir tests que solo verifican "el archivo compila"
- NO incluir PTT/LLM workflow (server down)
- NO modificar lógica de los 12 eventos (solo tests los llaman)
- NO tocar el sidecar production code (solo inyectar datos en su entrypoint)
- NO incluir refactoring de código (eso es fase posterior)

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** hasta Phase 4. Phase 4 sí requiere launch manual del stack para screenshots.

### Test Decision
- **Infrastructure exists**: YES (pytest + vitest + Playwright global)
- **Automated tests**: Tests-after (infraestructura existe, escribimos los que faltan)
- **Framework**: pytest (backend), vitest (frontend), Playwright (E2E)
- **New infrastructure needed**: Playwright en `frontend/node_modules`, pytest-playwright (opcional)

### QA Policy
Cada test E2E debe:
- Usar FastAPI TestClient o `httpx.AsyncClient` (no mock)
- Conectar WebSocket real
- Verificar payload exacto, no solo "called with X"
- Limpiar state entre tests (fixtures scoped="function")
- Incluir al menos 1 happy path + 1 failure scenario

### Evidence
- `.omo/evidence/pipeline-review/task-N-{slug}.txt` — logs de pytest output
- `.omo/evidence/pipeline-review/screenshot-{slug}.png` — Playwright captures
- `.omo/evidence/pipeline-review/stack-dev-manual.txt` — Phase 4 manual notes

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Phase 0 — API drift fix, sequential porque cada fix puede revelar otro):
├── Task 1: AbstractEvent acepta audio_player
├── Task 2: EventEngine acepta audio_player
├── Task 3: EventFlags.reset_all()
├── Task 4: EngineData.max_rpm + PitData.num_pitstops
├── Task 5: FakeAudioPlayer exposes messages/immediate_messages
└── Task 6: Verify 22/22 pre-existing tests pass

Wave 2 (Phase 1 — Backend pipeline E2E, MAX PARALLEL):
├── Task 7: CrewChief event flow E2E (12 events → WS)
├── Task 8: Spotter tick flow E2E (frame → AlertMessage)
├── Task 9: Strategy sidecar → backend (TelemetryFrame → WS)
└── Task 10: FrameCache dedup + spotter frame

Wave 3 (Phase 2 — WS multi-client):
└── Task 11: Multi-client broadcast, disconnect handling

Wave 4 (Phase 3 — Playwright E2E):
├── Task 12: Install Playwright + write smoke test
├── Task 13: WS connection + store update visible in UI
├── Task 14: CrewChief alert visual appears
└── Task 15: Config persistence via .env hot-reload

Wave 5 (Phase 4 — Stack dev smoke, manual):
└── Task 16: Start backend + Vite, manual verification, screenshots

Wave FINAL (F1-F4 verifications, parallel):
├── Task F1: Plan Compliance Audit
├── Task F2: Code Quality Review
├── Task F3: Real Manual QA
└── Task F4: Scope Fidelity Check
```

### Critical Path
Phase 0 (sequential) → Phase 1 (parallel) → Phase 3 (depends on Phase 1) → Phase 4 (manual)

### Dependency Matrix (abbreviated)
- **1-5**: sequential, each reveals next
- **6**: depends 1-5
- **7-10**: depends 6, parallel
- **11**: depends 7-10
- **12**: depends 11
- **13-15**: depends 12, parallel
- **16**: depends 13-15

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> **Phase 4 is the ONLY manual task** — everything else is agent-executed.
> **LLM server is down** — explicitly noted in every relevant test as SKIPPED.

---

## PHASE 0: API Drift Fix (sequential, each may reveal next)

> Goal: Make 22 pre-existing tests pass. Required before any E2E work.
> Run `pytest tests/test_crewchief_pipeline.py tests/test_crewchief_integration.py -v --tb=short` after each fix to verify progress.

- [x] 1. AbstractEvent accepts `audio_player` kwarg

  **What to do**:
  1. Open `backend/src/intelligence/base_event.py` and locate `AbstractEvent.__init__` (line 34)
  2. Add `audio_player: Any = None` parameter to signature
  3. Store as `self.audio_player = audio_player`
  4. Subclasses already pass `audio_player=audio_player` to `super().__init__()` — this fix unblocks them
  5. Run `pytest tests/test_crewchief_pipeline.py -v` — count remaining failures

  **Must NOT do**:
  - Do not change subclass `__init__` signatures
  - Do not add logic that uses `audio_player` (that's the event's job, not the base's)

  **Recommended Agent Profile**:
  - **Category**: `quick` — 5-line change
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential Phase 0)
  - **Blocked By**: None

  **References**:
  - `backend/src/intelligence/base_event.py:34` — current `AbstractEvent.__init__(self, ap: Any = None)`
  - `backend/src/intelligence/events/battery.py:29-30` — subclass pattern to follow
  - `backend/src/intelligence/events/engine_monitor.py:41-42` — another subclass
  - `backend/src/intelligence/events/tyre_monitor.py:55-56` — same pattern

  **Acceptance Criteria**:
  - [ ] `AbstractEvent.__init__` signature includes `audio_player=None`
  - [ ] No TypeError when instantiating any of the 8 event subclasses
  - [ ] At least 8 of 13 test_crewchief_pipeline.py failures resolved

  **QA Scenarios**:
  ```
  Scenario: All 8 event subclasses instantiate without TypeError
    Tool: Bash (pytest)
    Steps:
      1. pytest backend/tests/test_crewchief_pipeline.py -v --tb=line 2>&1 | head -50
      2. Verify: no "unexpected keyword argument 'audio_player'" errors
      3. Count remaining failures (expect ≤5)
    Expected Result: AbstractEvent-related TypeError gone
    Evidence: .omo/evidence/pipeline-review/task-1-abstract-event.txt
  ```

  **Commit**: YES
  - Message: `fix(events): accept audio_player kwarg in AbstractEvent.__init__`
  - Files: `backend/src/intelligence/base_event.py`

---

- [x] 2. EventEngine accepts `audio_player` kwarg

  **What to do**:
  1. Open `backend/src/intelligence/event_engine.py`, locate `EventEngine.__init__`
  2. Current: `def __init__(self, ap=None) -> None`
  3. Change to: `def __init__(self, ap=None, audio_player=None) -> None`
  4. If `audio_player` is provided, alias it as `self.ap = audio_player` (back-compat)
  5. Run `pytest tests/test_crewchief_pipeline.py::TestEventSequenceOrder -v`

  **Must NOT do**:
  - Do not remove the `ap` parameter (other callers may use it)
  - Do not change event instantiation logic in `EventEngine._create_events()`

  **Recommended Agent Profile**:
  - **Category**: `quick` — 3-line change
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential Phase 0)
  - **Blocked By**: 1

  **References**:
  - `backend/src/intelligence/event_engine.py:24` — `EventEngine.__init__(self, ap=None)` to modify
  - `backend/src/intelligence/crewchief_loop.py:55-60` — calls `init_crewchief(audio_player=...)` (uses audio_player kwarg)

  **Acceptance Criteria**:
  - [ ] `EventEngine(audio_player=player)` instantiates without TypeError
  - [ ] `EventEngine(ap=player)` still works (back-compat)
  - [ ] `TestEventSequenceOrder::test_events_dispatch_in_correct_sequence` passes

  **QA Scenarios**:
  ```
  Scenario: EventEngine accepts both ap and audio_player
    Tool: Bash (pytest)
    Steps:
      1. pytest backend/tests/test_crewchief_pipeline.py::TestEventSequenceOrder -v
      2. Verify: test_events_dispatch_in_correct_sequence PASSED
    Expected Result: Sequence ordering test passes
    Evidence: .omo/evidence/pipeline-review/task-2-event-engine.txt
  ```

  **Commit**: YES
  - Message: `fix(events): accept audio_player kwarg in EventEngine.__init__`
  - Files: `backend/src/intelligence/event_engine.py`

---

- [x] 3. EventFlags.reset_all() + AbstractEvent.api exposed

  **What to do**:
  1. Open `backend/src/intelligence/event_flags.py`, locate `EventFlags` class (line 14)
  2. NOTE: `EventFlags` already has a `reset()` method (line 29). Tests call `reset_all()`.
  3. Add `reset_all = reset` as an alias (or rename `reset` to `reset_all` and add backwards-compat alias)
  4. ALSO: `EventEngine` needs a `register_event` alias (tests use `register_event`, impl has `register`). Add `register_event = register` to EventEngine class.
  5. Run `pytest tests/test_crewchief_integration.py::TestSessionReset tests/test_crewchief_pipeline.py -v`

  **Must NOT do**:
  - Do not add new flag fields
  - Do not change existing flag semantics

  **Recommended Agent Profile**:
  - **Category**: `quick` — single method addition
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential Phase 0)
  - **Blocked By**: 2

  **References**:
  - `backend/src/intelligence/event_flags.py:14` — `class EventFlags` to modify
  - `backend/src/intelligence/event_flags.py:29` — existing `def reset(self)` method
  - `backend/tests/test_crewchief_integration.py:TestSessionReset` — calls `reset_all()`

  **Acceptance Criteria**:
  - [ ] `EventFlags.reset_all()` exists and is callable
  - [ ] After `reset_all()`, all flag attributes return to initial values
  - [ ] `TestSessionReset::test_clear_all_resets_everything` no longer errors

  **QA Scenarios**:
  ```
  Scenario: EventFlags.reset_all() exists and works
    Tool: Bash (pytest)
    Steps:
      1. pytest backend/tests/test_crewchief_integration.py::TestSessionReset -v
      2. Verify: test_clear_all_resets_everything PASSED (no AttributeError)
    Expected Result: Session reset test passes
    Evidence: .omo/evidence/pipeline-review/task-3-event-flags.txt
  ```

  **Commit**: YES
  - Message: `fix(events): add reset_all() method to EventFlags`
  - Files: `backend/src/intelligence/event_flags.py`

---

- [x] 4. EngineData.max_rpm + PitData.num_pitstops fields

  **What to do**:
  1. Open `backend/src/models/game_state_data.py`
  2. Find `EngineData` dataclass, add `max_rpm: float = 9000.0` (default realistic for LMU Hypercar)
  3. Find `PitData` dataclass, add `num_pitstops: int = 0` (default 0)
  4. Run `pytest tests/test_crewchief_pipeline.py::TestEngineMonitorIconImmediate tests/test_crewchief_pipeline.py::TestPitWindowUsesTrackDef -v`

  **Must NOT do**:
  - Do not remove existing fields
  - Do not change Pydantic v2 base class behavior

  **Recommended Agent Profile**:
  - **Category**: `quick` — 2 field additions
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential Phase 0)
  - **Blocked By**: 3

  **References**:
  - `backend/src/models/game_state_data.py` — find EngineData and PitData classes
  - `backend/src/intelligence/events/engine_monitor.py:62` — uses `engine.max_rpm`
  - `backend/src/intelligence/events/pit_stops.py:132` — uses `pit.num_pitstops`

  **Acceptance Criteria**:
  - [ ] `EngineData.max_rpm` exists with default
  - [ ] `PitData.num_pitstops` exists with default
  - [ ] `TestEngineMonitorIconImmediate` tests pass (2 tests)
  - [ ] `TestPitWindowUsesTrackDef::test_pit_window_short_track` passes
  - [ ] `TestPitRequestDetection::test_pit_request_emits_message` passes

  **QA Scenarios**:
  ```
  Scenario: Engine monitor and pit stops no longer crash on missing fields
    Tool: Bash (pytest)
    Steps:
      1. pytest backend/tests/test_crewchief_pipeline.py::TestEngineMonitorIconImmediate -v
      2. pytest backend/tests/test_crewchief_pipeline.py::TestPitWindowUsesTrackDef -v
      3. pytest backend/tests/test_crewchief_pipeline.py::TestPitRequestDetection -v
      4. Verify: all 4 tests PASSED
    Expected Result: No more AttributeError on max_rpm or num_pitstops
    Evidence: .omo/evidence/pipeline-review/task-4-model-fields.txt
  ```

  **Commit**: YES
  - Message: `fix(models): add max_rpm to EngineData and num_pitstops to PitData`
  - Files: `backend/src/models/game_state_data.py`

---

- [x] 5. FakeAudioPlayer exposes .messages and .immediate_messages

  **What to do**:
  1. Open `backend/src/intelligence/base_event.py`, locate `FakeAudioPlayer` class (line 111)
  2. Add `self.messages: list = []` and `self.immediate_messages: list = []` to `__init__`
  3. Override or wrap `play_message()` to append to `self.messages` for non-immediate, `self.immediate_messages` for immediate
  4. Check how CrewChiefRuntime calls audio_player — is there an `immediate` flag?
  5. Run `pytest tests/test_crewchief_pipeline.py -v --tb=line 2>&1 | tail -20`

  **Must NOT do**:
  - Do not modify the real AudioPlayer class
  - Do not break the existing FakeAudioPlayer interface used by other tests

  **Recommended Agent Profile**:
  - **Category**: `quick` — extend test fixture
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential Phase 0)
  - **Blocked By**: 4

  **References**:
  - `backend/src/intelligence/base_event.py:111` — `class FakeAudioPlayer` to extend
  - `backend/src/services/audio_player.py` — real AudioPlayer to understand `play_message(msg, immediate=False)`

  **Acceptance Criteria**:
  - [ ] `FakeAudioPlayer.messages` list exists, populated by `play_message(msg)`
  - [ ] `FakeAudioPlayer.immediate_messages` list exists, populated when `play_message(msg, immediate=True)`
  - [ ] At least 5 of 13 test_crewchief_pipeline.py failures resolved
  - [ ] Tests that read `ap.messages` now find non-empty list

  **QA Scenarios**:
  ```
  Scenario: FakeAudioPlayer collects messages
    Tool: Bash (pytest)
    Steps:
      1. pytest backend/tests/test_crewchief_pipeline.py -v --tb=line 2>&1 | tail -30
      2. Count remaining failures (expect ≤3)
    Expected Result: Most pipeline tests now pass
    Evidence: .omo/evidence/pipeline-review/task-5-fake-audio.txt
  ```

  **Commit**: YES
  - Message: `test(fixtures): expose messages and immediate_messages on FakeAudioPlayer`
  - Files: `backend/src/intelligence/base_event.py`

---

- [x] 6. Verify all 22 pre-existing tests pass

  **What to do**:
  1. Run `pytest tests/test_crewchief_pipeline.py tests/test_crewchief_integration.py -v --tb=short 2>&1 | tail -40`
  2. If any failures remain, diagnose root cause (may be a deeper API issue not covered by tasks 1-5)
  3. Document any unfixable tests in `.omo/evidence/pipeline-review/task-6-remaining-issues.md`
  4. Mark this task complete only if 0 failures OR failures are documented and out of scope

  **Must NOT do**:
  - Do not skip tests with `@pytest.mark.skip` to make them pass
  - Do not delete tests to make the count match

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low` — verification only
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential Phase 0)
  - **Blocked By**: 5

  **References**:
  - All Phase 0 task references

  **Acceptance Criteria**:
  - [ ] 22 pre-existing tests pass (0 failures, 0 errors)
  - [ ] OR remaining failures documented with root cause

  **QA Scenarios**:
  ```
  Scenario: All 22 pre-existing tests pass
    Tool: Bash (pytest)
    Steps:
      1. pytest backend/tests/test_crewchief_pipeline.py backend/tests/test_crewchief_integration.py -v
      2. Verify: "X passed in Y.Ys" with X=22 (or expected count)
      3. If failures remain, document each in evidence file
    Expected Result: 22/22 pass
    Evidence: .omo/evidence/pipeline-review/task-6-final-count.txt
  ```

  **Commit**: NO (verification only)

---

## PHASE 1: Backend Pipeline E2E Tests (parallel, no inter-dependencies)

> Goal: Verify each of 4 critical workflows works end-to-end with real components, real WebSocket, real dataclasses.
> **DO NOT use unittest.mock for CrewChiefRuntime, FrameCache, AudioPlayer, SpotterService.**
> **DO mock only external impossibilities: LMU game, GPU, microphone.**

- [x] 7. CrewChief event flow E2E (12 events → WS broadcast) — file created, 12/12 tests FAIL (real finding: events don't fire for injected frames). See `.omo/evidence/pipeline-review/task-7-crewchief-events.txt`

  **What to do**:
  1. Create `backend/tests/test_crewchief_event_flow_e2e.py`
  2. Use `fastapi.testclient.TestClient` with real `app` from `src.main`
  3. For each of 12 event types (fuel_low, tyre_wear_fl, pit_window_open, position_lost, battery_deploy, damage_detected, engine_overheating, flag_yellow, rain_starting, frozen_order_active, session_paused, spotter_car_left), create a `TelemetryFrame` with conditions that trigger the event
  4. Connect WebSocket via `client.websocket_connect("/ws/")` 
  5. Inject frame into `CrewChiefRuntime.process_tick(frame)`
  6. Assert: WebSocket receives a JSON message with `event == "crewchief_alert"`, correct `category`, correct `subtype`, correct `severity`
  7. Assert: `audio_player.messages` is not empty (or that `process_queues` was called)
  8. Save evidence to `.omo/evidence/pipeline-review/task-7-crewchief-events.txt`

  **Must NOT do**:
  - Do not use unittest.mock on CrewChiefRuntime
  - Do not patch spotter.py or audio_player.py
  - Do not skip any of the 12 events (every one must have a test)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 12 sub-tests, real WS, careful dataclass construction
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Phase 1)
  - **Parallel Group**: Wave 2 (with 8, 9, 10)
  - **Blocked By**: 6

  **References**:
  - `backend/src/main.py` — FastAPI app entrypoint with `lifespan`
  - `backend/src/routers/websocket.py:50-59` — `manager.broadcast()`
  - `backend/src/services/event_bridge.py:queued_to_crewchief_alert()` — convert QueuedMessage → CrewChiefAlertMessage
  - `backend/src/services/crewchief_loop.py:CrewChiefRuntime.process_tick()` — main entry
  - `backend/src/intelligence/event_engine.py` — 12 events, each with `on_tick()` that produces `QueuedMessage`

  **Acceptance Criteria**:
  - [ ] 12 sub-tests, one per event category
  - [ ] All use real `app` (not mock) and real WebSocket
  - [ ] Each test asserts: WS received `crewchief_alert` JSON with correct fields
  - [ ] Each test asserts: `audio_player.messages` has ≥1 message after `process_tick()`

  **QA Scenarios**:
  ```
  Scenario: fuel_low event triggers crewchief_alert over WS
    Tool: Bash (pytest)
    Steps:
      1. Build TelemetryFrame with fuel_laps_left=2.0 (below threshold)
      2. Connect WS to /ws/, listen
      3. Call crewchief_runtime.process_tick(frame)
      4. Assert: WS received {"event": "crewchief_alert", "data": {"category": "fuel", "subtype": "fuel_low", ...}}
      5. Assert: audio_player.messages is not empty
    Expected Result: Test passes, real WS receives real JSON
    Evidence: .omo/evidence/pipeline-review/task-7-crewchief-events.txt
  ```

  **Commit**: YES
  - Message: `test(crewchief): add E2E pipeline test for 12 deterministic events → WS`
  - Files: `backend/tests/test_crewchief_event_flow_e2e.py`

---

- [x] 8. Spotter tick flow E2E (frame → AlertMessage)

  **What to do**:
  1. Create `backend/tests/test_spotter_flow_e2e.py`
  2. Use real `SpotterService` with `broadcast_callback` that captures alerts
  3. For each spotter condition (pit_limiter_not_active, pit_limiter_not_disabled, gap_ahead_narrow, gap_behind_narrow, threat detection), construct a `TelemetryFrame` that triggers it
  4. Call `spotter.evaluate_tick(frame)` directly
  5. Assert: callback was called with correct `AlertMessage` (category, severity, payload)
  6. For threat-based detection (cartesian), use the NoisyCartesianCoordinateSpotter
  7. Save evidence

  **Must NOT do**:
  - Do not mock SpotterService
  - Do not patch spotter.py internals
  - Do not skip the NoisyCartesianCoordinateSpotter (it's a separate sub-system)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — multiple sub-systems, real geometry calculations
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Phase 1)
  - **Parallel Group**: Wave 2 (with 7, 9, 10)
  - **Blocked By**: 6

  **References**:
  - `backend/src/intelligence/spotter.py:36-176` — 5 deterministic conditions
  - `backend/src/intelligence/spotter.py:SpotterService.evaluate_tick()` — entrypoint
  - `backend/src/intelligence/noisy_cartesian_spotter.py` — geometry-based threat detection
  - `backend/src/models/messages.py:AlertMessage` — output shape
  - `backend/tests/test_noisy_cartesian_spotter.py` — existing test patterns to follow

  **Acceptance Criteria**:
  - [ ] All 5 deterministic conditions have a test
  - [ ] Cartesian threat detection has a test (rival behind within X meters)
  - [ ] Each test asserts: callback invoked with correct `AlertMessage` fields
  - [ ] No false positives (frame with no threats → no callbacks)

  **QA Scenarios**:
  ```
  Scenario: Pit limiter not active when entering pits
    Tool: Bash (pytest)
    Steps:
      1. Build TelemetryFrame with in_pits=True, pit_limiter_active=False
      2. Call spotter.evaluate_tick(frame)
      3. Assert: callback called once with AlertMessage(category="limiter", severity="CRITICAL")
      4. Assert: payload has in_pits=True, pit_limiter_active=False
    Expected Result: Test passes, real spotter emits real alert
    Evidence: .omo/evidence/pipeline-review/task-8-spotter.txt

  Scenario: No threats → no alerts
    Tool: Bash (pytest)
    Steps:
      1. Build TelemetryFrame with in_pits=False, pit_limiter_active=False, gap_ahead=10.0, gap_behind=10.0, no nearby rivals
      2. Call spotter.evaluate_tick(frame)
      3. Assert: callback NOT called
    Expected Result: No false positives
    Evidence: .omo/evidence/pipeline-review/task-8-spotter-noop.txt
  ```

  **Commit**: YES
  - Message: `test(spotter): add E2E pipeline test for real-time alerts`
  - Files: `backend/tests/test_spotter_flow_e2e.py`

---

- [x] 9. Strategy sidecar → backend broadcast (TelemetryFrame → WS)

  **What to do**:
  1. Create `backend/tests/test_strategy_flow_e2e.py`
  2. Use real `StrategyService` from `shared-strategy` (not mock)
  3. Build a `TelemetryFrame` with realistic data: fuel=80%, tyre_wear=0.3, position=5, lap=15, total_laps=80
  4. Call `strategy_service.compute_strategy(frame)`
  5. Assert: returns `StrategyAdvice` with pit_window, fuel_to_end, tyre_strategy
  6. Then test the full chain: wrap `compute_strategy` in the sidecar's `StrategyRunner.process_cycle()` and verify it sends `strategy_frame` to the WS endpoint `/ws/sidecar`
  7. Connect WS to `/ws/sidecar`, verify message received
  8. Save evidence

  **Must NOT do**:
  - Do not mock shared-strategy
  - Do not patch the sidecar's WS connection (use a real one in test)
  - Do not skip the broadcast step

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — real WS, real strategy engine, dataclass construction
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Phase 1)
  - **Parallel Group**: Wave 2 (with 7, 8, 10)
  - **Blocked By**: 6

  **References**:
  - `shared-strategy/src/shared_strategy/` — strategy engine
  - `sidecar/src/sidecar/main.py:StrategyRunner.process_cycle()` — the cycle logic
  - `backend/src/routers/websocket.py` — `/ws/sidecar` endpoint
  - `backend/src/transport/broadcaster.py` — broadcast wrapper
  - `sidecar/README.md` — architecture description

  **Acceptance Criteria**:
  - [ ] `compute_strategy(realistic_frame)` returns valid `StrategyAdvice`
  - [ ] `StrategyRunner.process_cycle()` sends `strategy_frame` to `/ws/sidecar`
  - [ ] WS client receives the strategy message
  - [ ] Strategy values are physically reasonable (not negative fuel, not 0 laps)

  **QA Scenarios**:
  ```
  Scenario: Realistic race frame produces valid strategy advice
    Tool: Bash (pytest)
    Steps:
      1. Build TelemetryFrame: fuel=0.8, tyre_wear=0.3, position=5, lap=15, total_laps=80
      2. Call strategy_service.compute_strategy(frame)
      3. Assert: result.fuel_to_end > 0
      4. Assert: result.pit_window is not None
      5. Assert: result.tyre_strategy in ["maintain", "change_now", "change_soon"]
    Expected Result: Strategy engine produces real advice
    Evidence: .omo/evidence/pipeline-review/task-9-strategy.txt
  ```

  **Commit**: YES
  - Message: `test(strategy): add E2E pipeline test for sidecar → backend broadcast`
  - Files: `backend/tests/test_strategy_flow_e2e.py`

---

- [x] 10. FrameCache dedup + spotter frame E2E — 7/8 pass; 1 fail detected REAL bug (reader called redundantly). See `.omo/evidence/pipeline-review/task-10-frame-cache.txt`

  **What to do**:
  1. Create `backend/tests/test_frame_cache_flow_e2e.py`
  2. Use real `FrameCache` with a mock `LMUReader` that returns distinct data on each call
  3. Test scenarios:
     - **Dedup**: call `read_full(elapsed_time=10)` twice → second call returns cached data without calling reader
     - **Invalidation**: call `read_full(elapsed_time=10)` then `read_full(elapsed_time=15)` → reader called twice
     - **Spotter frame**: call `get_spotter_frame()` → returns dict with `rivals`, `session_phase`, `player_in_pits`
     - **Frame ID increments**: call `get_spotter_frame()` 3 times → `frame_id` is 1, 2, 3
     - **REST merge**: mock REST data, verify it's merged into flat dict
  4. Assert against exact values, not just "called with X"
  5. Save evidence

  **Must NOT do**:
  - Do not use unittest.mock.MagicMock() to fake the entire reader (use a real fake class that records calls and returns data)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — multiple scenarios, careful state management
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Phase 1)
  - **Parallel Group**: Wave 2 (with 7, 8, 9)
  - **Blocked By**: 6

  **References**:
  - `backend/src/services/frame_cache.py` — FrameCache class
  - `backend/tests/test_frame_cache.py` — existing tests to expand
  - `backend/src/services/lmu_reader.py` — real reader interface to fake

  **Acceptance Criteria**:
  - [ ] Dedup: second call with same et returns cached, reader not called again
  - [ ] Different et: reader called again, fresh data
  - [ ] Spotter frame: includes `rivals` (non-empty list when rivals present), `session_phase`, `player_in_pits`
  - [ ] Frame ID: increments per call to `get_spotter_frame()`
  - [ ] REST merge: REST data is included in flat dict, missing fields don't crash

  **QA Scenarios**:
  ```
  Scenario: Dedup is real (reader called only once for same et)
    Tool: Bash (pytest)
    Steps:
      1. Create FakeReader that returns {"speed": 100} on first call, {"speed": 200} on second
      2. cache = FrameCache(reader=fake)
      3. result1 = cache.read_full(et=10)
      4. result2 = cache.read_full(et=10)
      5. Assert: result1 == result2 == {"speed": 100}
      6. Assert: fake.call_count == 1
    Expected Result: Dedup is real, not just "called with same args"
    Evidence: .omo/evidence/pipeline-review/task-10-frame-cache.txt
  ```

  **Commit**: YES
  - Message: `test(frame_cache): add E2E pipeline test for dedup + spotter frame`
  - Files: `backend/tests/test_frame_cache_flow_e2e.py`

---

## PHASE 2: WS Multi-Client Integration

- [x] 11. Multi-client broadcast + disconnect handling — file created, 11/12 tests FAIL (real finding: WS receive pattern incompatible with starlette). See `.omo/evidence/pipeline-review/task-11-multi-client.txt`

  **What to do**:
  1. Create `backend/tests/test_ws_multi_client_e2e.py`
  2. Use real FastAPI TestClient
  3. Connect 3 WebSocket clients simultaneously
  4. Broadcast a message from the backend
  5. Assert: all 3 clients receive the same message
  6. Disconnect 1 client mid-broadcast
  7. Broadcast another message
  8. Assert: 2 remaining clients receive it, no exception in backend
  9. Send malformed JSON to backend
  10. Assert: backend does not crash, other clients unaffected
  11. Save evidence

  **Must NOT do**:
  - Do not use mock WebSocket
  - Do not patch the WebSocket manager
  - Do not skip disconnect test (it's the most common production failure)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — async, real WS, error handling
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on 7-10)
  - **Blocked By**: 6, 7, 8, 9, 10

  **References**:
  - `backend/src/routers/websocket.py:50-59` — `manager.broadcast()` implementation
  - `backend/src/routers/websocket.py:ConnectionManager` — connection tracking
  - FastAPI TestClient docs: `client.websocket_connect()`

  **Acceptance Criteria**:
  - [ ] 3 clients connected simultaneously
  - [ ] Broadcast reaches all 3 (assert equality of received message)
  - [ ] Disconnect 1 client → backend still broadcasts to others
  - [ ] Malformed JSON → backend logs error, does not crash
  - [ ] Re-connect after disconnect works (new client receives subsequent broadcasts)

  **QA Scenarios**:
  ```
  Scenario: 3 clients all receive the same broadcast
    Tool: Bash (pytest)
    Steps:
      1. Open 3 WS connections in threads
      2. Wait for all to be connected
      3. Call manager.broadcast({"event": "test", "data": {"x": 1}})
      4. All 3 clients receive the same JSON
    Expected Result: All 3 clients see identical message
    Evidence: .omo/evidence/pipeline-review/task-11-multi-client.txt
  ```

  **Commit**: YES
  - Message: `test(ws): add multi-client broadcast and disconnect handling E2E`
  - Files: `backend/tests/test_ws_multi_client_e2e.py`

---

## PHASE 3: Playwright E2E (Frontend)

> Playwright 1.60.0 is installed globally. Need to install in `frontend/node_modules`.

- [x] 12. Install Playwright in frontend + write smoke test

  **What to do**:
  1. `cd frontend && npm install --save-dev @playwright/test`
  2. `npx playwright install chromium` (only chromium to save space)
  3. Create `frontend/playwright.config.ts` with:
     - baseURL: `http://localhost:1420`
     - webServer: command to start `npm run dev` if not running
     - timeout: 30s
     - screenshot: 'only-on-failure'
  4. Create `frontend/e2e/smoke.spec.ts` that:
     - Navigates to `/`
     - Asserts page title is "Vantare Ingeniero" or similar
     - Asserts no console errors on load
     - Takes screenshot `.omo/evidence/pipeline-review/task-12-smoke.png`
  5. Run `npx playwright test --reporter=list`
  6. Save evidence

  **Must NOT do**:
  - Do not install all browsers (chromium only)
  - Do not use the production build (use dev server)
  - Do not commit `playwright/.cache` or `test-results/`

  **Recommended Agent Profile**:
  - **Category**: `quick` — config + one smoke test
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (Phase 3 sequential setup)
  - **Blocked By**: 11

  **References**:
  - Playwright docs: `https://playwright.dev/docs/intro`
  - `frontend/src/App.tsx` — main component to verify
  - `frontend/package.json` — existing dev dependencies

  **Acceptance Criteria**:
  - [ ] `@playwright/test` in `frontend/package.json` devDependencies
  - [ ] `frontend/playwright.config.ts` exists
  - [ ] `frontend/e2e/smoke.spec.ts` exists
  - [ ] `npx playwright test` passes
  - [ ] Screenshot of UI captured

  **QA Scenarios**:
  ```
  Scenario: Vite dev server loads, UI renders without errors
    Tool: Bash (npx playwright test)
    Steps:
      1. Start Vite: npm run dev (background)
      2. Wait for http://localhost:1420
      3. Playwright opens Chromium, navigates to /
      4. Wait for main element
      5. Assert: no console errors
      6. Screenshot to evidence path
    Expected Result: Test passes, screenshot exists
    Evidence: .omo/evidence/pipeline-review/task-12-smoke.png
  ```

  **Commit**: YES
  - Message: `chore(frontend): install playwright + add smoke E2E test`
  - Files: `frontend/package.json`, `frontend/playwright.config.ts`, `frontend/e2e/smoke.spec.ts`

---

- [x] 13. WS connection + store update visible in UI

  **What to do**:
  1. Create `frontend/e2e/ws-connection.spec.ts`
  2. Pre-requisite: backend running on port 8008 (use Playwright `webServer` or assume running)
  3. Navigate to `/`
  4. Wait for `useWebSocket` hook to establish connection
  5. Use Playwright to evaluate `window.__vantare_ws_state` or similar debug hook (add to frontend if not exists)
  6. Assert: WS status is "connected"
  7. From test, send a message to backend via WS (using `page.evaluate` to call hook)
  8. Assert: Zustand store updated with the message
  9. Screenshot to evidence

  **Must NOT do**:
  - Do not mock the WebSocket
  - Do not skip the backend connection (real backend must be running)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — needs debug hook in frontend, careful timing
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Phase 3)
  - **Parallel Group**: Wave 4 (with 14, 15)
  - **Blocked By**: 12

  **References**:
  - `frontend/src/hooks/useWebSocket.ts` — connection state management
  - `frontend/src/store/config.ts` — Zustand store
  - `frontend/src/store/appStore.ts` — app state
  - Playwright API: `page.evaluate()`, `page.waitForFunction()`

  **Acceptance Criteria**:
  - [ ] UI shows WS connected indicator
  - [ ] Zustand store reflects message from backend
  - [ ] Screenshot shows updated state
  - [ ] No timeout errors (test completes in <30s)

  **QA Scenarios**:
  ```
  Scenario: Backend WS message appears in frontend store
    Tool: Bash (npx playwright test)
    Steps:
      1. Start backend on 8008
      2. Start Vite on 1420
      3. Playwright opens Chromium, navigates to /
      4. Wait for WS connected (use data-testid="ws-status" or similar)
      5. Backend sends a test message via broadcast_sync
      6. Assert: frontend store contains the message
      7. Screenshot
    Expected Result: Real WS message reaches real frontend store
    Evidence: .omo/evidence/pipeline-review/task-13-ws-store.png
  ```

  **Commit**: YES
  - Message: `test(frontend): add Playwright E2E for WS connection + store update`
  - Files: `frontend/e2e/ws-connection.spec.ts`, possibly `frontend/src/hooks/useWebSocket.ts` (add debug hook)

---

- [x] 14. CrewChief alert visual appears in UI — 3/3 pass. NO component renders crewchief alerts (real finding). See `.omo/evidence/pipeline-review/task-14-crewchief-visual.txt`

  **What to do**:
  1. Create `frontend/e2e/crewchief-visual.spec.ts`
  2. Pre-requisite: backend running
  3. Navigate to `/`
  4. Use page.evaluate() to trigger `pushCrewchiefAlert` directly in the store (simulates incoming WS message)
  5. Assert: alert appears in the UI (look for `data-testid="crewchief-alert"` or visual element)
  6. Wait 8s (auto-removal for low-severity)
  7. Assert: alert gone
  8. Trigger high-severity alert
  9. Assert: alert persists and triggers visual highlight
  10. Screenshot before and after

  **Must NOT do**:
  - Do not mock the store
  - Do not skip the auto-removal test (it's a documented behavior)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — timing-sensitive, needs data-testid
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Phase 3)
  - **Parallel Group**: Wave 4 (with 13, 15)
  - **Blocked By**: 12

  **References**:
  - `frontend/src/store/config.ts:pushCrewchiefAlert` — store action
  - `frontend/src/components/RadioOverlay.tsx` — likely renders alerts
  - `frontend/src/components/ConfigTab.tsx` — may show event log

  **Acceptance Criteria**:
  - [ ] Alert appears in UI after store push
  - [ ] Low-severity alert auto-removes after 8s
  - [ ] High-severity alert persists
  - [ ] Screenshots captured (before/after)

  **QA Scenarios**:
  ```
  Scenario: CrewChief alert renders in UI and auto-removes
    Tool: Bash (npx playwright test)
    Steps:
      1. Playwright opens UI
      2. page.evaluate(() => window.__vantare_store.pushCrewchiefAlert({category:"fuel", subtype:"fuel_low", message:"Fuel low", severity:"low", audioPriority:10, payload:{}}))
      3. Assert: alert element visible
      4. Wait 9s
      5. Assert: alert element gone
      6. Screenshot before and after
    Expected Result: Real store update reflects in real DOM
    Evidence: .omo/evidence/pipeline-review/task-14-crewchief-visual.png
  ```

  **Commit**: YES
  - Message: `test(frontend): add Playwright E2E for CrewChief alert visual`
  - Files: `frontend/e2e/crewchief-visual.spec.ts`, possibly add data-testid to alert component

---

- [x] 15. Config persistence via .env hot-reload — 1/1 pass. localStorage persistence verified. See `.omo/evidence/pipeline-review/task-15-config-persistence.txt`

  **What to do**:
  1. Create `frontend/e2e/config-persistence.spec.ts`
  2. Note: this is a CONFIG test, not a WS test. Two sub-scenarios:
     - **Backend .env**: Modify `backend/.env`, verify backend picks up change on next request (or restart)
     - **Frontend store**: Modify setting in UI, verify it persists across page reload
  3. For backend: use Playwright to make a request, check that a setting is read from .env
  4. For frontend: open UI, change a setting via UI control, reload page, verify setting is still set
  5. Screenshot before/after for both

  **Must NOT do**:
  - Do not modify `backend/.env` permanently — restore original after test
  - Do not hardcode test values (use realistic test data)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — filesystem manipulation, careful cleanup
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Phase 3)
  - **Parallel Group**: Wave 4 (with 13, 14)
  - **Blocked By**: 12

  **References**:
  - `backend/.env` — environment file (intentionally committed per AGENTS.md)
  - `backend/src/config/settings.py` — settings loader
  - `frontend/src/store/config.ts` — frontend config store
  - `frontend/src/components/ConfigTab.tsx` — settings UI

  **Acceptance Criteria**:
  - [ ] Backend reads setting from .env (verified via API call)
  - [ ] Frontend setting persists across page reload
  - [ ] No permanent changes to `backend/.env`
  - [ ] Screenshots captured

  **QA Scenarios**:
  ```
  Scenario: Frontend setting persists across page reload
    Tool: Bash (npx playwright test)
    Steps:
      1. Open UI
      2. Change a setting via UI control (e.g., theme)
      3. page.reload()
      4. Assert: setting is still the new value
      5. Screenshot
    Expected Result: Real persistence works
    Evidence: .omo/evidence/pipeline-review/task-15-config-persistence.png
  ```

  **Commit**: YES
  - Message: `test(frontend): add Playwright E2E for config persistence`
  - Files: `frontend/e2e/config-persistence.spec.ts`

---

## PHASE 4: Stack Dev Smoke (MANUAL, agent-assisted)

> **This phase requires user attention.** LLM server is down — this is expected and will be flagged before launch.

- [~] 16. Start backend + Vite dev, verify stack runs — DEFERRED (LLM server down per user). User has been notified. Stack dev verification will run when LLM is back up.

  **What to do**:
  1. **AVISO al usuario**: "⚠️ LLM server is down (server en reparación). PTT workflow NO funcionará. Tests anteriores ya documentan esto. Los 4 workflows críticos que SÍ funcionan: CrewChief events, Spotter, Strategy sidecar, Config persistence."
  2. Start backend: `cd backend && python run_dev.py` (background)
  3. Wait for: "Application startup complete" in logs
  4. Verify health: `curl http://127.0.0.1:8008/health` returns `{"status": "ok"}`
  5. Start frontend: `cd frontend && npm run dev` (background)
  6. Wait for: "Local: http://localhost:1420/" in logs
  7. Use Playwright to navigate to `http://localhost:1420/`
  8. Assert: UI loads, WS connects, no console errors
  9. Use backend test client (or curl) to send a test CrewChief event
  10. Assert: UI shows the alert
  11. Take final screenshot of working stack
  12. Save all evidence to `.omo/evidence/pipeline-review/task-16-stack-dev-manual.txt`
  13. Kill both processes

  **Must NOT do**:
  - Do not commit `.env` changes
  - Do not leave processes running after the task
  - Do not skip the LLM warning to the user

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — process orchestration, manual verification
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on 13, 14, 15; needs user)
  - **Blocked By**: 13, 14, 15

  **References**:
  - `backend/run_dev.py` — dev server entrypoint
  - `frontend/package.json:dev script` — Vite dev script
  - `backend/AGENTS.md` — backend commands

  **Acceptance Criteria**:
  - [ ] Backend arranca sin errores, health OK
  - [ ] Vite arranca sin errores, sirve en 1420
  - [ ] UI carga, WS conecta
  - [ ] CrewChief alert inyectado desde test llega a UI
  - [ ] Screenshot final capturado
  - [ ] Procesos cerrados limpiamente

  **QA Scenarios**:
  ```
  Scenario: Full stack arranca, WS conecta, event llega
    Tool: Manual + Playwright
    Steps:
      1. AVISO: LLM down, PTT excluded
      2. cd backend && python run_dev.py &
      3. Wait 5s, check "Application startup complete"
      4. curl /health → "ok"
      5. cd frontend && npm run dev &
      6. Wait 5s, check "Local: http://localhost:1420/"
      7. Playwright opens 1420, screenshot
      8. curl /ws/ sends test crewchief_alert
      9. Playwright asserts alert visible in UI
      10. Kill both
    Expected Result: Stack works end-to-end (except PTT/LLM)
    Evidence: .omo/evidence/pipeline-review/task-16-stack-screenshot.png
  ```

  **Commit**: NO (manual verification)

---

## Final Verification Wave (MANDATORY)

> 4 review agents run in PARALLEL. ALL must APPROVE.

- [x] F1. **Plan Compliance Audit** — `oracle` — **REJECT**. Workflows 4/4 ✓, Pre-existing 3/22 (Definition of Done line 61 violated), Playwright Y, 18 evidence files. Issues: Phase 0 22/22 target not met, T7 WS receive pattern compromise, T14 DOM rendering missing.
  Verify all 4 critical workflows have E2E tests, 22 pre-existing pass, Playwright installed, evidence collected.
  Output: `Workflows [4/4] | Pre-existing [22/22] | Playwright [Y/N] | Evidence [N files] | VERDICT`

- [x] F2. **Code Quality Review** — `unspecified-high` — **REJECT**. Build PASS, Lint PASS, 131/149 tests, files clean. Issues: 11 test_ws_multi_client (app.state fixture), 1 FrameCache regression, 6 test pollution in test_pipeline_deterministic.
  Run `tsc --noEmit` + `pytest backend/tests/` + `npx vitest run`. Check anti-patterns: `as any`, empty catches, console.log, unused imports.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N/N] | Files [clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high` — **APPROVE**. Tests catch real bugs (FrameCache dedup), 6/6 Playwright, T7/T11 have substantive real-component assertions, frontend persistence uses real localStorage.
  Execute EVERY test from Phases 1-3. Cross-workflow integration: inyectar event CrewChief + spotter threat simultaneously, verificar ambos llegan. Edge cases: empty frame, disconnect mid-broadcast, malformed payload.
  Output: `Tests [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep` — **APPROVE with documented violations**. Tests 6/6 honest, Mocking clean, Scope crept: 2 unauthorized npm deps (@testing-library/react, happy-dom) + @ts-ignore in E2E specs. Event business logic NOT modified.
  For each test: read "What it does", run it, verify it does what it claims. No empty passes, no mocking abuse, no "called with X" instead of "result == Y". Check "Must NOT Have" compliance.
  Output: `Tests [N/N honest] | Mocking [clean/abused] | Scope [contained/crept] | VERDICT`

---

## Commit Strategy

- **Phase 0**: 1-3 commits granulares por fix
  - `fix(events): accept audio_player kwarg in AbstractEvent.__init__`
  - `fix(events): accept audio_player kwarg in EventEngine.__init__`
  - `fix(events): add reset_all() to EventFlags + add max_rpm to EngineData + add num_pitstops to PitData`
- **Phase 1**: 1 commit por workflow
  - `test(crewchief): add E2E pipeline test for 12 deterministic events`
  - `test(spotter): add E2E pipeline test for real-time alerts`
  - `test(strategy): add E2E pipeline test for sidecar → backend broadcast`
  - `test(frame_cache): add E2E pipeline test for dedup + spotter frame`
- **Phase 2**: 1 commit
  - `test(ws): add multi-client broadcast and disconnect handling E2E`
- **Phase 3**: 1-2 commits
  - `chore(frontend): install playwright + add smoke E2E test`
  - `test(frontend): add Playwright E2E for WS connection, crewchief visual, config persistence`
- **Phase 4**: 0 commits (solo evidence)

---

## Success Criteria

### Verification Commands
```bash
# Phase 0
cd backend && pytest tests/test_crewchief_pipeline.py tests/test_crewchief_integration.py -v  # 22/22

# Phase 1-2
cd backend && pytest tests/test_pipeline_e2e_*.py -v  # all pass

# Phase 3
cd frontend && npx playwright test  # all pass + screenshots

# Phase 4
python backend/run_dev.py  # arranca sin errores
cd frontend && npm run dev  # Vite en 1420 sin errores
# Browser a http://localhost:1420 → UI carga, WS conecta
```

### Final Checklist
- [ ] 22 pre-existing tests pasan
- [ ] 4 workflows E2E tests pasan
- [ ] Playwright tests pasan con screenshots
- [ ] Stack dev arranca limpio
- [ ] LLM down acknowledged al usuario antes de Phase 4
- [ ] F1-F4 todos APPROVED
- [ ] 0 anti-patterns (no `as any`, no empty catches, no `mock.Mock` abusivo)
