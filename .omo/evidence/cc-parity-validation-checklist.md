# Crew Chief Parity Validation Checklist

**Plan:** Task 14 · [`crewchief-parity-port.md`](../../docs/superpowers/plans/2026-06-07-crewchief-parity-port.md)  
**Wave 7 cutover:** Task 48 · [`2026-06-08-crewchief-task48-cutover-validation.md`](../../docs/superpowers/plans/2026-06-08-crewchief-task48-cutover-validation.md)  
**Matriz:** [`.omo/evidence/cc-behavior-parity-matrix.yaml`](./cc-behavior-parity-matrix.yaml)  
**Ceilings:** [`docs/architecture/cc-permanent-ceilings.md`](../../docs/architecture/cc-permanent-ceilings.md)  
**Cierre LMU:** [`.omo/evidence/task-14-lmu-closure.md`](./task-14-lmu-closure.md) (2026-06-08)  
**Automated gate:** ver sección [Comandos de verificación](#comandos-de-verificación)

---

## Required Runtime

- [x] Backend reiniciado tras cambios de código.
- [x] `VANTARE_NATIVE_TELEMETRY=1` en backend (no sidecar).
- [x] `/health` → `telemetry.source` = `native`.
- [x] Sidecar **eliminado** (Task 49-S9; no existe ruta legacy).
- [x] LMU REST API alcanzable en `LMU_REST_URL` (pit menu, session settings).
- [x] `session_type_int` visible en telemetría WebSocket.
- [x] `speakOnlyWhenSpokenTo` desactivado salvo caso de prueba explícito.
- [x] `enableCommentaryBatch` = `false` (default post Task 48; ruta B opt-in).
- [ ] Binario Tauri reconstruido si se prueba app empaquetada (Task 49-S8 release smoke).

---

## Wave 7 — Legacy cutover (Task 48)

### Automated gates (2026-06-08)

- [x] `test_crewchief_no_legacy_emitters.py` — proactive/triggers no emiten IDs CC-owned.
- [x] `test_crewchief_wave7_cutover.py` — commentary batch OFF por defecto.
- [x] `test_replay_trace.py` + `scripts/replay_trace.py` — timeline determinista desde `.trace`.
- [x] `proactive_monitors.py` — solo estado interno (comeback pearl); sin `race_start` / `lap_complete`.
- [x] `get_all_triggers()` — solo `WeatherChangeTrigger`, `PhaseChangedTrigger`, `PilotQuestionTrigger`.
- [x] `cutover_registry.py` — `LEGACY_COMMENTARY_EVENT_IDS` = `phase_changed`, `weather_forecast`.
- [x] **169** tests `pytest -k crewchief` PASS.
- [x] `verify_alpha_parity.py` PASS (incluye gate Wave 7).

### Manual replay (opcional)

- [ ] `python backend/scripts/replay_trace.py backend/tests/fixtures/replay/minimal_race.trace --hz 20` → JSON con `event_id` de posición/vuelta.
- [ ] Comparar timeline replay vs sesión LMU corta (mismos `event_id` en adelantamiento / lap 2).

### Legacy allowlist (cerrada)

| event_id | Fuente permitida post-48 |
|----------|---------------------------|
| `phase_changed` | `PhaseChangedTrigger` LLM |
| `weather_forecast` | `WeatherChangeTrigger` forecast delta |

Todo lo demás determinista → `CrewChiefEventSuite` @ 20 Hz.

---

## A/B Scenarios (manual LMU)

### Practice Silence

- [x] Iniciar práctica LMU.
- [x] Verificar: sin mensajes race-only de posición, pit, gap o push-now del ingeniero.
- [x] Verificar: flags y lluvia siguen hablando si aplican.

### Race Start

- [x] Iniciar carrera.
- [x] Spotter no habla durante formation lap manual (si aplica).
- [x] Mensaje de salida / green una vez en verde.

### FCY

- [x] Activar FCY / SC.
- [x] Verificar secuencia: pits closed → pits open → prepare green → green (módulo flags).

### Penalty

- [x] Recibir penalización.
- [x] Verificar mensajes 3/2/1 vueltas, pit-now, served/expired (módulo penalties).

### Damage

- [x] Provocar impacto.
- [x] Verificar aviso inmediato + resumen de daños tras settle.

### Rain

- [x] Cambiar lluvia en vivo (`raininess` / wetness).
- [x] Verificar mensaje determinista sin depender solo de forecast LLM.

### Position / Overtake

- [x] Completar adelantamiento.
- [x] Un mensaje determinista vía `PositionEvent` @ 20 Hz (no commentary batch mezclado).

### Commentary batch (post-48)

- [x] Con `enableCommentaryBatch=false` (default): sin `commentary_end` proactivo en carrera.
- [x] Opt-in UI: activar batch solo para pruebas legacy / forecast LLM.

### Playback

- [x] Encolar mensaje NORMAL, luego IMMEDIATE.
- [x] IMMEDIATE interrumpe NORMAL; mensajes expirados no suenan.

### PTT Tool-First (Task 13)

- [x] **"Cállate" / "shhh"** → respuesta rápida, silencio total (spotter + proactivo), sin streaming largo.
- [x] **"¿Cuánto combustible?"** → datos reales (tool), no alucinación.
- [x] **"¿Cómo va mi ritmo?"** → streaming LLM (pregunta abierta).
- [x] **"Spot" / "don't spot"** → ack spotter (tool backend).
- [x] **"¿Cómo están los neumáticos?"** → `get_tire_wear`.
- [x] **"¿Hay daños?"** → `get_damage_report`.
- [x] **"Add 10 litres"** → `set_pit_fuel` (dry-run: mensaje simulación, sin POST LMU).

---

## Comandos de verificación

### Backend (pytest Task 14 gate)

```powershell
cd "C:\Users\isaac\Desktop\Vantare-Ingeniero\backend"
python -m pytest `
  tests/test_crewchief_event_types.py `
  tests/test_crewchief_session_gates.py `
  tests/test_crewchief_suite_engine.py `
  tests/test_crewchief_playback_policy.py `
  tests/test_crewchief_flags_module.py `
  tests/test_crewchief_penalties_module.py `
  tests/test_crewchief_rain_module.py `
  tests/test_crewchief_damage_module.py `
  tests/test_crewchief_fuel_module.py `
  tests/test_crewchief_timings_module.py `
  tests/test_crewchief_opponents_module.py `
  tests/test_lmu_pit_menu_write.py `
  tests/test_pilot_ptt_agent.py `
  tests/test_pilot_ptt_tools_13c.py `
  tests/test_crewchief_commands.py `
  tests/test_session_race_gating.py `
  tests/test_immediate_routing.py `
  -v
```

### Frontend (playback expiry)

```powershell
cd "C:\Users\isaac\Desktop\Vantare-Ingeniero\frontend"
npm test -- priorityAudioQueue.test.ts priorityAudioQueue.crewchief.test.ts
```

### Smoke integrado (sin LMU)

```powershell
cd "C:\Users\isaac\Desktop\Vantare-Ingeniero"
python scripts/verify_alpha_parity.py
python scripts/verify_audio_pipeline.py
```

### Wave 7 cutover gate (Task 48)

```powershell
cd "C:\Users\isaac\Desktop\Vantare-Ingeniero\backend"
python -m pytest tests/test_crewchief_no_legacy_emitters.py tests/test_crewchief_wave7_cutover.py tests/test_replay_trace.py -v
python -m pytest -k "crewchief" -q
python scripts/replay_trace.py tests/fixtures/replay/minimal_race.trace --hz 20
```

---

## Criterio MATCH vs PARTIAL

| Estado | Significado |
|--------|-------------|
| **MATCH** | Validado en LMU en vivo o replay determinista |
| **PARTIAL** | Tests unitarios + comportamiento aproximado; gap CC conocido |
| **MISMATCH** | Gap conductual conocido o no portado (p. ej. gaps con voz CC) |

---

## Task 14 closure (Tasks 1–13)

| Área | Tests | Validación LMU |
|------|-------|----------------|
| Event types + gates | `test_crewchief_event_types`, `test_crewchief_session_gates` | **OK** 2026-06-08 |
| Suite @ 20 Hz | `test_crewchief_suite_engine` | **OK** |
| Playback / expiry | `test_crewchief_playback_policy`, frontend queue tests | **OK** |
| Flags / FCY | `test_crewchief_flags_module`, `test_fcy_wave1` | **OK** |
| Penalties | `test_crewchief_penalties_module`, `test_penalty_wave1` | **OK** |
| Rain | `test_crewchief_rain_module`, `test_rain_wave1` | **OK** |
| Damage | `test_crewchief_damage_module`, `test_damage_wave1` | **OK** |
| Fuel / timings / opponents | `test_crewchief_fuel_module`, etc. | **OK** (LLM path) |
| Pit menu write | `test_lmu_pit_menu_write` | Dry-run PTT OK; POST live pendiente beta |
| PTT agent | `test_pilot_ptt_agent`, `test_pilot_ptt_tools_13c` | **OK** |
| Spotter state machine | `test_spotter_e2e`, `test_spotter_state` | **OK** (wired 2026-06-08) |
| Speak-only | `test_crewchief_commands`, `test_verbosity_controller` | **OK** |

---

## Resultados automatizados

| Suite | Resultado |
|-------|-----------|
| Backend Task 14 gate (~67 tests) | **PASS** |
| Wave 7 cutover (no-legacy + replay + batch OFF) | **PASS** (2026-06-08) |
| `pytest -k crewchief` | **169 PASS** (2026-06-08) |
| `pytest -q` (excl. `test_event_store`) | **841 PASS**, 16 FAIL pre-alpha debt (2026-06-08) |
| Frontend `priorityAudioQueue.crewchief` (2 tests) | **PASS** (2026-06-08) |
| `verify_alpha_parity.py` | **PASS** (2026-06-08) |
| `test_engine_runtime_config` (spotter snapshot) | **PASS** (fix Task 3 alpha) |

**Task 14:** cerrada para alpha — evidencia LMU en [task-14-lmu-closure.md](./task-14-lmu-closure.md).  
**Task 48:** cutover legacy cerrado en código + gates pytest; replay harness disponible.  
**Task 49:** native telemetry **DONE** (S0–S9, 2026-06-08) — sidecar removed; ver [native-telemetry-smoke.md](./native-telemetry-smoke.md).

### Task 49-S9 closure (2026-06-08)

- [x] Paquete `sidecar/` eliminado (source + binaries Tauri).
- [x] Ruta `/ws/sidecar` eliminada; `test_no_sidecar_endpoint.py` PASS.
- [x] `latest_strategy_frame` eliminado de app state.
- [x] Dev default: 2 procesos (backend + Tauri), `scripts/dev.ps1`.
- [x] `verify_alpha_parity.py` incluye gate native + no-sidecar.
- [ ] Release smoke empaquetado (Task 49-S6) — manual post-rebuild.
