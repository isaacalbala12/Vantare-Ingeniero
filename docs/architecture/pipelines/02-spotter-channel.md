# Pipeline — Canal Spotter (paridad CC)

## Objetivo de paridad

Reproducir **`NoisyCartesianCoordinateSpotter` + callbacks en `Spotter.cs`**: misma detección, mismos delays, mismo hold-repeat, mismos silencios en quali/salida — texto vía TTS en lugar de WAV `car_left/`.

**Matriz:** LMU-01 … LMU-05 (+ parte de LMU-06–09 según ítem).

## CC: cuándo habla el spotter

| Mensaje | Dispara (CC) | Timing CC | Vantare | Paridad |
|---------|--------------|-----------|---------|---------|
| Car left / right | overlap lateral, speed > 10 m/s | hold-repeat **3 s** | `SPOTTER_HOLD_REPEAT_S` | MATCH |
| Clear left/right/all | carsOnLeft/Right → 0 | delay **150 ms**, expiry 2 s | `SPOTTER_CLEAR_DELAY_S` | MATCH |
| Three-wide / in the middle | ambos lados | bounce **0.5–2 s** | hold_repeat/2 | MATCH |
| Pit limiter engage | entrada boxes, limiter off | grace **~3 s** | `PIT_LIMITER_GRACE_S` | MATCH |
| Pit limiter disengage | salida, limiter on | check **~2 s** | `PIT_LIMITER_EXIT_CHECK_S` | MATCH |

## CC: qué NO es spotter (ingeniero en CC)

Estos ítems a veces están en `spotter.py` Vantare pero en CC van por **Events** (canal ingeniero). Alinear según matriz:

| Tema | Canal CC | Vantare actual | Acción paridad |
|------|----------|----------------|----------------|
| Fuel crítico / fumes | `Fuel.cs` ingeniero p10 | `_eval_fuel_critical` spotter | Revisar canal + mensajes LMU-06 |
| SC / FCY fases | `FlagsMonitor.cs` | `_eval_safety_car` spotter + flags_monitor | Fases completas LMU-15 |
| Last lap | `SessionEndMessages` / LapCounter | `_eval_last_lap` spotter | OK edge; texto + canal |
| Damage multicomponente | `DamageReporting.cs` | `_eval_damage` spotter | Extender LMU-09 |
| Gap pegado | `Timings` / spotter opcional | UI-only gaps | LMU-10 toggle |

## Frecuencia de evaluación

| | CC | Vantare objetivo | Vantare hoy |
|--|-----|------------------|-------------|
| Evaluación | Cada GameState | **20 Hz** | 20 Hz `telemetry_sender_loop` ✓ |
| Input | Mismo GameState | Mismo `TelemetryFrame` dict | `frame_to_spotter_tick` ✓ |

## Propiedades = timings (mapeo)

| CC property | Default | Vantare config |
|-------------|---------|----------------|
| `min_speed_for_spotter` | 10 m/s | `spotterMinSpeedMs` |
| `spotter_hold_repeat_frequency` | 3 s | `spotterHoldRepeatS` |
| `spotter_clear_delay` | 150 ms | `spotterClearDelayS` |
| `spotter_overlap_delay` | 2000 ms | `spotterOverlapDelayS` |
| `time_after_race_start_for_spotter` | 20 s | `spotterRaceStartDelayS` |
| `spotterOffQualifying` | configurable | `spotterOffQualifying` |

WS `config_update` → `SpotterService.apply_runtime_config()`.

## Gates (no hablar)

Alineados con CC `getNextMessage` / `isMessageStillValid`:

- `in_pits` (lateral)
- velocidad < min
- qualifying si spotter off
- race start delay 20 s
- FCY spotter pause 10–30 s (**LMU-40**, CC `fcySpotterCooldownWindow`) — **P1 deuda**
- `competitors` vacío

## Salida Vantare

```
SpotterService.evaluate_tick → AlertMessage (event=alert)
  → audio_priority → frontend IMMEDIATE
  → priorityAudioQueue.enqueueImmediate
  → TTS
```

Equivalente CC: `SoundType.IMPORTANT_MESSAGE` + `playMessageImmediately`.

## Archivos

| Archivo | Rol |
|---------|-----|
| `spotter.py` | Reglas + `_eval_*` |
| `spotter_state.py` | Máquina lateral, 3-wide, clear |
| `cartesian_spotter.py`, `spotter_geometry.py` | Geometría CC-style |
| `spotter_adapter.py` | Frame → tick |
| `personality_pack.py`, `spotter_phrases_es.json` | Texto TTS |
| `websocket.py` | Loop 20 Hz |

## Texto (WAV → TTS)

CC usa carpetas WAV por spotter pack. Vantare:

- Plantillas ES por perfil (`formal` / `standard` / `aggressive`)
- Mismo **punto semántico**: “clear left”, no parafrasear LLM

## Verificación

- `scripts/verify_spotter_pipeline.py`
- `backend/tests/test_spotter*.py`
- `.omo/evidence/spotter-lmu-validation.md`
- Matriz LMU-01–05: `paridad: MATCH`

## Deuda P0/P1 (conductual)

1. **Lateral invertido** — path_lateral + ori_fwd + state machine completa (LMU-01 delta).
2. **FCY pause spotter** — cooldown ventana SC (LMU-40).
3. **Mover mensajes ingeniero** fuera de spotter donde CC usa Events.
4. **Message expiry 2 s** en cola si playback retrasado (LMU-02).
