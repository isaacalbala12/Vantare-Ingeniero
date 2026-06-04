# CrewChief V4: Revision Masiva de Tests

## TL;DR

> **Quick Summary**: Auditoria completa del sistema de tests del CrewChief V4. Hay 70 tests pasando y 3 fallando (todos en test_frame_cache.py). La cobertura existe para la mayoria de componentes pero hay 11 gaps: 4 eventos sin tests, pipeline sin e2e, validaciones cross-SP pendientes.
>
> **Deliverables**:
> - Fix de 3 tests fallando en SP1
> - Tests para 4 eventos huerfanos: lap_counter, position, flags_monitor, session_monitor
> - Test e2e full pipeline: LMUReader -> FrameCache -> GameStateBuilder -> EventEngine -> AudioPlayer -> WebSocket
> - Tests cross-boundary: spotter<->frame_cache, bridge<->audio, audio<->sound
>
> **Estimated Effort**: Large (7 tasks + 4 verification waves)
> **Parallel Execution**: YES, 2 waves
> **Critical Path**: Task 1 -> Task 4 -> Task 7

---

## Context

### Original Request
"Create a comprehensive test review plan for the CrewChief V4 system."

### Current State

**Test landscape** (70 passing, 3 failing):
- **SP1 (Pipeline de datos)**: test_frame_cache.py (10 tests, 3 failing), test_lmu_reader.py, test_state_diff.py, test_delta_time.py, test_track_definition.py, test_car_class_data.py, test_game_state_builder.py, test_game_state_data.py, test_enums.py
- **SP2 (Audio system)**: test_audio_player.py, test_audio_player_broadcast.py, test_sound_cache.py, test_number_reader.py, test_colloquial_time.py, test_utilities.py
- **SP3 (Spotter)**: test_noisy_cartesian_spotter.py, test_spotter.py, test_spotter_messages.py, test_coordinate_math.py
- **SP4 (EventEngine)**: test_event_engine.py, test_base_event.py, test_base_events.py, test_event_flags.py, test_event_store.py
- **SP5 (Events)**: 8 de 12 eventos con tests. 4 huerfanos: lap_counter, position, flags_monitor, session_monitor
- **SP6 (Frontend Integration)**: test_crewchief_integration.py, test_crewchief_pipeline.py, test_crewchief_ws_integration.py, test_messages_crewchief.py, test_broadcaster.py, test_msgpack_codec.py

**3 tests failing** (all in test_frame_cache.py):
| Test | Linea | Sintoma | Causa raiz |
|------|-------|---------|------------|
| test_read_full_returns_dict | 48 | KeyError on place | Mock no incluye place. El reader real si. |
| test_dedup_same_et_doesnt_call_reader | 62 | call_count=3 instead of 1 | _merge_rest() ejecuta 3 veces, o dedup no cachea bien |
| test_spotter_frame_id_increments | 120 | frame_id no incrementa | get_spotter_frame() no re-llama read_full() |

**Silent failures detectados**:
1. **Dedup roto**: Condition check en L18-L19 retorna temprano pero _merge_rest() en L21 se ejecuta de todos modos. O _last_et se actualiza antes del check. Necesita debug.
2. **Missing place key**: FrameCache no anade place, depende del reader.
3. **frame_id estatico**: Solo incrementa en read_full(), no en get_spotter_frame().

### Key Research Findings
- FrameCache.read_full() L15-44: logica de dedup correcta en intencion pero rota en practica
- FrameCache._merge_rest() L51-67: no se saltea cuando se usa cache, datos REST quedan stale
- 4 eventos sin tests unitarios: lap_counter, position, flags_monitor, session_monitor
- Pipeline completo no tiene test end-to-end

---

## Work Objectives

### Core Objective
Auditar, reparar, y completar la cobertura de tests del sistema CrewChief V4 para que los 6 sub-proyectos tengan tests que verifiquen su contrato, sus integraciones cruzadas, y el pipeline completo end-to-end.

### Concrete Deliverables
1. backend/tests/test_frame_cache.py - 3 tests reparados + 2 tests nuevos de regresion
2. backend/tests/test_lap_counter.py - tests para lap_counter
3. backend/tests/test_position.py - tests para position
4. backend/tests/test_flags_monitor.py - tests para flags_monitor
5. backend/tests/test_session_monitor.py - tests para session_monitor
6. backend/tests/test_pipeline_e2e.py - test full pipeline SP1->SP6
7. Cross-boundary tests (spotter<->frame, bridge<->audio, audio<->sound)

### Definition of Done
- [ ] 3 tests fallando reparados + sin regresiones
- [ ] 4 nuevos archivos de test para eventos huerfanos pasando
- [ ] Test e2e del pipeline completo pasando (SP1->SP6)
- [ ] pytest backend/tests/ -q -> todos pasan, >= 100 tests total
- [ ] Cada evento SP5 tiene al menos 3 tests unitarios
- [ ] Zero regresiones en los 70 tests existentes

### Must Have
- Los 3 tests fallando deben pasar
- Cada uno de los 12 eventos SP5 debe tener tests unitarios
- El pipeline e2e debe verificar que un frame produce una alerta categorizable
- Zero regresiones
- Tests ejecutables por agente sin intervencion humana

### Must NOT Have (Guardrails)
- NO modificar la logica de negocio de los eventos (solo escribir tests)
- NO modificar el comportamiento runtime de FrameCache (arreglar bug, no cambiar contrato)
- NO modificar los modelos de mensajes existentes
- NO anadir dependencias de test nuevas
- NO romper tests del frontend
- NO eliminar tests existentes

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (pytest + vitest + conftest.py con fixtures)
- **Automated tests**: Tests-first para Task 1. Tests-after para Tasks 2-6.
- **Framework**: pytest (backend), vitest (frontend)

### QA Policy
Every task MUST include agent-executed QA scenarios.
- **Backend**: pytest para tests unitarios y de integracion
- **All verification**: comandos bash ejecutables, no pasos manuales

---

## Execution Strategy

### Parallel Execution Waves

Wave 1 (Foundation, fix + fill gaps):
|--- Task 1: Fix SP1 FrameCache [quick]
|--- Task 2: SP2 audio pipeline tests [quick]
|--- Task 3: SP3 spotter integration tests [quick]

Wave 2 (Events + Integration, MAX PARALLEL):
|--- Task 4: SP4 EventEngine integration tests [quick]
|--- Task 5: SP5 comprehensive tests for all 12 events [unspecified-high]
|--- Task 6: SP6 frontend integration tests [quick]

Wave FINAL:
|--- Task 7: Full pipeline e2e test [unspecified-high]

Wave VERIFICATION:
|--- F1: Plan compliance audit (oracle)
|--- F2: Code quality + tests (unspecified-high)
|--- F3: Execute all QA scenarios (unspecified-high)
|--- F4: Scope fidelity check (deep)

---


## TODOs

- [ ] 1. Fix SP1 FrameCache, dedup roto + missing keys + frame_id estatico

  **What to do**:
  1. Debug test_dedup_same_et_doesnt_call_reader (L56-62): el assert call_count == 1 falla con 3. Verificar si _merge_rest() en L21 se ejecuta incluso cuando se retorna cache en L19.
  2. Reparar test_read_full_returns_dict (L48): anadir place: 3 al _base del MockReader.
  3. Reparar test_spotter_frame_id_increments (L120): el test debe llamar read_full() antes del segundo get_spotter_frame().
  4. Anadir 2 tests de regresion: test_dedup_preserves_rest_data, test_frame_id_increments_on_read_full.

  **Must NOT do**: NO cambiar contrato publico de FrameCache, NO eliminar tests existentes

  **Agent Profile**: quick
  **Parallel**: NO (foundation, bloquea Task 7)
  **Blocks**: 7

  **References**:
  - backend/src/services/frame_cache.py:7-44
  - backend/tests/test_frame_cache.py:42-81, 84-135
  - backend/src/services/lmu_reader.py

  **Acceptance Criteria**:
  - [ ] test_read_full_returns_dict pasa
  - [ ] test_dedup_same_et_doesnt_call_reader pasa (call_count == 1)
  - [ ] test_spotter_frame_id_increments pasa
  - [ ] 2 tests de regresion nuevos pasando
  - [ ] pytest backend/tests/test_frame_cache.py -v -> 12/12

  **QA Scenarios**:
  - Scenario Dedup: pytest test_dedup_same_et_doesnt_call_reader -v. Expected call_count == 1. Evidence: task-1-dedup-fix.txt
  - Scenario frame_id: pytest test_spotter_frame_id_increments -v. Expected sf2.frame_id > sf1.frame_id. Evidence: task-1-frame-id-fix.txt

  **Evidence**: task-1-dedup-fix.txt, task-1-frame-id-fix.txt, task-1-no-regression.txt
  **Commit**: fix(sp1): repair FrameCache dedup, missing keys, and frame_id increment

---

- [ ] 2. SP2 Audio Pipeline, completar cobertura de integracion audio

  **What to do**:
  1. Revisar test_audio_player.py, test_audio_player_broadcast.py: cubren play_message -> broadcast? Cubren NullAudioOutput? Cubren preemption?
  2. Anadir tests: priority_queue_order, null_output_doesnt_crash, empty_queue_no_error, broadcast_on_play
  3. Revisar test_sound_cache.py: fallback WAV ausente? caching?

  **Must NOT do**: NO modificar AudioPlayer, NO depender de PyAudio real

  **Agent Profile**: quick
  **Parallel**: YES (con Task 1 y 3)
  **Blocks**: 7

  **References**: backend/src/services/audio_player.py, backend/tests/test_audio_player*.py, backend/tests/test_sound_cache.py

  **Acceptance Criteria**:
  - [ ] 4 tests nuevos pasando
  - [ ] Path play_message -> broadcast verificado
  - [ ] pytest backend/tests/test_audio_player*.py backend/tests/test_sound_cache.py -v -> todos pasan

  **QA Scenarios**:
  - Scenario Priority: pytest test_audio_player_priority_queue_order -v. Expected spotter (prio 20) antes que normal (prio 5). Evidence: task-2-priority-order.txt

  **Evidence**: task-2-priority-order.txt, task-2-null-output.txt, task-2-all-tests.txt
  **Commit**: test(sp2): complete audio pipeline test coverage

---

- [ ] 3. SP3 Spotter, tests de integracion con frame_cache

  **What to do**:
  1. Anadir tests: receives_spotter_frame_from_cache, rivals_transform_correctly, empty_rivals_no_crash, multiple_rivals_ordering
  2. Revisar test_coordinate_math.py: distancia, angulo, bordes

  **Must NOT do**: NO modificar spotter, NO modificar formato rival data

  **Agent Profile**: quick
  **Parallel**: YES (con Task 1 y 2)
  **Blocks**: 7

  **References**: backend/src/intelligence/noisy_cartesian_spotter.py, backend/tests/test_noisy_cartesian_spotter.py, backend/tests/test_coordinate_math.py

  **Acceptance Criteria**:
  - [ ] 4 tests de integracion pasando
  - [ ] Casos borde: 0 rivals, 20 rivals, misma posicion

  **QA Scenarios**:
  - Scenario: pytest test_spotter_receives_spotter_frame_from_cache -v. Expected integracion funciona. Evidence: task-3-spotter-cache.txt

  **Evidence**: task-3-spotter-cache.txt, task-3-empty-rivals.txt, task-3-all-tests.txt
  **Commit**: test(sp3): add spotter-frame_cache integration tests

---

- [ ] 4. SP4 EventEngine, tests de integracion con eventos y flags

  **What to do**:
  1. Anadir tests: dispatches_all_registered_events, respects_sequence_order, skip_inapplicable, timeout_doesnt_block_loop, auto_disable_after_max_fail
  2. Revisar test_event_flags.py: reset_all()? flags compartidos?

  **Must NOT do**: NO modificar dispatch, NO modificar AbstractEvent

  **Agent Profile**: quick
  **Parallel**: YES (con Task 5 y 6)
  **Blocks**: 7

  **References**: backend/src/intelligence/event_engine.py, backend/src/intelligence/base_event.py, backend/tests/test_event_engine.py

  **Acceptance Criteria**:
  - [ ] 5 tests de integracion pasando
  - [ ] Cobertura: timeout, auto-disable, orden, filtro

  **QA Scenarios**:
  - Scenario: pytest test_event_engine_dispatches_all_registered_events -v. Expected 3 eventos mock reciben trigger_internal. Evidence: task-4-dispatch.txt

  **Evidence**: task-4-dispatch.txt, task-4-timeout.txt, task-4-all-tests.txt
  **Commit**: test(sp4): add EventEngine integration tests



- [ ] 5. SP5 Events, tests completos para los 12 eventos

  **What to do**:

  **Parte A: 4 eventos huerfanos**
  1. test_lap_counter.py (5 tests): new_lap, same_lap, out_lap, in_lap, clear_state
  2. test_position.py (5 tests): gain, loss, leader, start, overtake
  3. test_flags_monitor.py (4 tests): yellow, green, fcy, clear_state
  4. test_session_monitor.py (4 tests): formation_start, formation_end, session_change, chequered

  **Parte B: 8 eventos existentes**
  5. Verificar >=3 tests cada uno, anadir casos borde y clear_state

  **Must NOT do**: NO modificar eventos, NO asumir valores de shared memory

  **Agent Profile**: unspecified-high (4 archivos nuevos + revision 8 existentes)
  **Parallel**: YES (con Task 4 y 6)
  **Blocks**: 7

  **References**: backend/src/intelligence/events/*.py, backend/tests/test_fuel.py (ejemplo patron)

  **Acceptance Criteria**:
  - [ ] 4 archivos nuevos con >=18 tests total
  - [ ] 12/12 eventos con >=3 tests

  **QA Scenarios**:
  - Scenario: pytest test_lap_counter.py test_position.py test_flags_monitor.py test_session_monitor.py -v. Expected >=18 tests, 0 failures. Evidence: task-5-new-events.txt

  **Evidence**: task-5-new-events.txt, task-5-existing-coverage.txt, task-5-all-events.txt
  **Commit**: test(sp5): add tests for lap_counter, position, flags_monitor, session_monitor

---

- [ ] 6. SP6 Frontend Integration, tests de bridge + WebSocket + store

  **What to do**:
  1. Anadir tests bridge: all_categories, severity_mapping, preserves_payload, handles_none_name
  2. Frontend vitest si faltan: pushCrewchiefAlert, latestByCategory, max 20 events, TTS queue

  **Must NOT do**: NO modificar _CATEGORY_MAP, NO modificar store/handler

  **Agent Profile**: quick
  **Parallel**: YES (con Task 4 y 5)
  **Blocks**: 7

  **References**: backend/src/services/event_bridge.py, frontend/src/store/config.ts, frontend/src/hooks/useWebSocket.ts

  **Acceptance Criteria**:
  - [ ] 4 tests de bridge pasando
  - [ ] 12 categorias verificadas, 5 niveles de severity

  **QA Scenarios**:
  - Scenario: pytest test_bridge_queued_to_alert_all_categories -v. Expected 12 categorias mapeadas. Evidence: task-6-categories.txt

  **Evidence**: task-6-categories.txt, task-6-severity.txt, task-6-all-tests.txt
  **Commit**: test(sp6): complete frontend integration tests

---

- [ ] 7. Full Pipeline Integration Test, LMUReader -> WebSocket

  **What to do**:
  1. Crear backend/tests/test_pipeline_e2e.py:
     - test_full_pipeline_frame_to_alert: frame -> CrewChiefAlertMessage en WS
     - test_pipeline_multiple_frames_state_evolution: 10 frames, estado evoluciona
     - test_pipeline_handles_empty_frame: no crashea
     - test_pipeline_session_transition_resets_flags: PRACTICE->RACE, reset_all()
     - test_pipeline_spotter_message_reaches_ws: spotter -> WebSocket
  2. Mocks: LMUReader, WebSocket manager, NullAudioOutput

  **Must NOT do**: NO WS real, NO shared memory real, NO audio_dir real

  **Agent Profile**: unspecified-high
  **Parallel**: NO (depende de Tasks 1-6)
  **Blocked By**: 1, 2, 3, 4, 5, 6

  **References**: backend/src/services/crewchief_loop.py, backend/tests/conftest.py

  **Acceptance Criteria**:
  - [ ] 5 tests e2e pasando
  - [ ] pytest backend/tests/test_pipeline_e2e.py -v -> 5/5

  **QA Scenarios**:
  - Scenario: pytest test_full_pipeline_frame_to_alert -v. Expected event=crewchief_alert, categoria valida. Evidence: task-7-pipeline-e2e.txt

  **Evidence**: task-7-pipeline-e2e.txt, task-7-multi-frame.txt, task-7-empty-frame.txt
  **Commit**: test(e2e): add full pipeline integration test LMUReader->WebSocket

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE.

- [ ] F1. **Plan Compliance Audit** (oracle): Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT
- [ ] F2. **Code Quality + Tests** (unspecified-high): pytest >=100 tests, 0 failures | VERDICT
- [ ] F3. **Real QA Execution** (unspecified-high): Execute EVERY QA scenario. Edge cases. Save to .sisyphus/evidence/final-qa/
- [ ] F4. **Scope Fidelity Check** (deep): Coverage [N/12 events] | VERDICT

---

## Commit Strategy

- **1**: fix(sp1): repair FrameCache dedup, missing keys, and frame_id increment
- **2**: test(sp2): complete audio pipeline test coverage
- **3**: test(sp3): add spotter-frame_cache integration tests
- **4**: test(sp4): add EventEngine integration tests
- **5**: test(sp5): add tests for 4 missing events; complete coverage
- **6**: test(sp6): complete frontend integration tests
- **7**: test(e2e): add full pipeline integration test

---

## Success Criteria

- [x] **C1**: 3/3 tests en test_frame_cache.py pasan
- [x] **C2**: 12/12 eventos SP5 con >=3 tests
- [x] **C3**: Pipeline e2e SP1->SP6 verificado
- [x] **C4**: Cross-SP integration tested
- [x] **C5**: Zero regressions (70 tests existing)
- [x] **C6**: >=100 total tests
- [x] **C7**: Agent-executable verification
- [x] **C8**: >=2 evidence files per task
