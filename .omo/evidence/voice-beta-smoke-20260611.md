# Voice Beta Smoke — 2026-06-11

Smoke evidence tras Hito 6 (cierre beta voice re-architecture).  
**Revisión orquestador:** suite completa green post-fix (1016 backend + 277 frontend).

## Resultados V1–V6

| ID | Resultado | Evidencia |
|----|-----------|-----------|
| V1 | PASS (auto) | `test_spotter_to_voice_queue` — proximidad → PlayCommand IMMEDIATE. Audio manual pendiente (backend + Edge TTS en pista). |
| V2 | PASS | `test_v2_cc_evaluates_on_race_tick_without_websocket` |
| V3 | PASS | `test_v3_voice_loop_crash_does_not_stop_race_tick` — excepción en player, race sigue |
| V4 | PASS | `test_v4_spotter_eval_once_per_tick_regardless_of_ws_clients` — via `run_race_tick_once` |
| V5 | PASS | `test_v5_pilot_question_does_not_block_race_tick` |
| V6 | PASS (auto) | `verify_beta_gate.ps1` exit 0. `doctor.ps1` con `-WithDoctor` si backend :8008 |

## Comandos GATE (post-fix orquestador)

```
cd backend && python -m pytest -q --tb=no
# 1016 passed
```

```
cd frontend && npm test -- --run
# 277 passed (46 files)
```

```
powershell -ExecutionPolicy Bypass -File scripts\verify_beta_gate.ps1
# Beta gate PASSED (incluye pytest full backend)
```

## Fixes orquestador (post entrega agente)

| Fix | Motivo |
|-----|--------|
| `NATIVE_TELEMETRY` en `config.py` | 15 tests fallaban en `/health` y WS integration |
| `test_config_sync_ws` expect `min(10, 5)` | Cap intencional en `spotter.apply_runtime_config` |
| `test_native_telemetry_frame_source` hub=None | MagicMock hub bypass evitaba `snapshot_frame` |
| V3/V4 tests reforzados | Crash real en player; V4 usa `run_race_tick_once` |
| `verify_beta_gate.ps1` + full pytest | Gate no debe pasar con 16 tests rojos |

## Audio manual (V1)

- [ ] Config → Probar audio (backend) audible
- [ ] Spotter proximity sin doble TTS frontend (`voiceBackendPlayback=true`)

## Post-beta

- Fase 2-R1 ProcessPool: gated; medir p95 race_loop en pista antes de activar
- doctor.ps1: `-WithDoctor` en verify_beta_gate cuando backend bundle esté up
