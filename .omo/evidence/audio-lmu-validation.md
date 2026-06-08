# Checklist LMU — Pipeline de audio y triggers

Validación manual en pista. Marca cada fila tras probarla en sesión real.

**Stack:** backend `:8008`, telemetría **native** (sin sidecar), Tauri app, LMU en carrera/práctica.

| # | Origen | Condición para provocar | Evento WS | ¿Voz? | Prioridad | ¿Preempt? | OK |
|---|--------|-------------------------|-----------|-------|-----------|-----------|-----|
| 1 | Spotter | Rival lateral en recta | `alert` proximity | Sí | IMMEDIATE | — | ✅ |
| 2 | Spotter | Rival se aleja lateralmente | `alert` clear / clear_all | Sí | IMMEDIATE | — | ✅ |
| 3 | Spotter | Coches ambos lados | `alert` three-wide (`in_the_middle`) | Sí | IMMEDIATE | — | ✅ |
| 4 | Spotter | Entrar boxes sin limiter (vel > 1 m/s, grace 1.5s) | `alert` limiter engage | Sí | IMMEDIATE | — | ✅ |
| 5 | Spotter | Salir boxes con limiter ON (delay 2s) | `alert` limiter disengage | Sí | IMMEDIATE | — | ✅ |

> **Defaults CC (Jun 2026):** filas 1–5 validadas en pista (2026-06-08). Limiter grace 3s, exit check 2s. State machine spotter wired Jun 2026.

| 6 | Spotter | Fuel < 1 vuelta | `alert` fuel (una vez) | Sí | IMMEDIATE | — | ✅ |
| 7 | Spotter | SC / FCY | `alert` safety_car / flags CC | Sí | IMMEDIATE | — | ✅ |
| 8 | Spotter | Última vuelta carrera | `alert` session (una vez) | Sí | IMMEDIATE | — | ✅ |
| 9 | Spotter | Impacto / daño | `alert` damage (impacto) + CC | Sí | IMMEDIATE | — | ✅ |
| 10 | Spotter | Gap < 0.5s | `alert` gaps | **No** (solo UI) | — | — | ✅ |
| 11 | Ingeniero | Frenos > 80% desgaste | `alert` strategy (edge-once) | Sí | IMMEDIATE | — | ☐ |
| 12 | Ingeniero | Clase rápida detrás (multiclass) | `alert` strategy (por escenario) | Sí | IMMEDIATE | — | ☐ |
| 13 | Ingeniero | Penalización nueva | `alert` strategy (edge) | Sí | IMMEDIATE | — | ☐ |

> **Filas 6–10:** validar en carrera extensa. **Filas 11–13:** gates en `test_audio_trigger_matrix.py` + `test_triggers.py`. Ciclo ingeniero @ 0.5 Hz (no 20 Hz).

| 14 | Ingeniero | Fuel < 3 vueltas | `llm_pending` → `advice_*` | Sí | NORMAL | Spotter corta | ✅ edge + fin carrera |
| 15 | Ingeniero | SC / bandera | `llm_pending` → `advice_*` | Sí | NORMAL | Spotter corta | ✅ edge transición |
| 16 | Ingeniero | Ventana boxes abierta | `llm_pending` → `advice_*` | Sí | NORMAL | Spotter corta | ✅ edge-once |
| 17 | Piloto | PTT pregunta combustible | `advice_*` | Sí | NORMAL | Spotter corta | ✅ CI PTT→llm_pending |
| 18 | Piloto | PTT mientras ingeniero habla | — | Nueva respuesta | NORMAL | `advice_start` limpia cola NORMAL | ✅ CI preemption |
| 19 | Spotter | Durante respuesta LLM larga | `alert` proximity | Sí | IMMEDIATE | Corta audio NORMAL | ✅ CI cola audio |
| 20 | Sistema | Ducking LMU | — | Volumen juego baja ~65% | — | — | ✅ impl (Windows) |
| 21 | Config | Spotter off qualifying | — | Sin lateral en quali | — | — | ✅ CI + toggle UI |
| 22 | Voz | "Activa el spotter" | `alert` spotter | **No** (solo UI) | — | — | ✅ category spotter |
| 23 | Ingeniero | Cambio posición / vuelta | `commentary_end` | Sí | NORMAL | Spotter corta | ✅ CI monitors |
| 24 | Ingeniero | Perla (vuelta rápida) | `alert` pearl | Sí | NORMAL (priority 2) | Spotter corta | ✅ CI engine |

**Estado evidencia (Jun 2026):** Task 14 cerrada — validación LMU 2026-06-08 ([task-14-lmu-closure.md](task-14-lmu-closure.md)). Gates CI verdes (`verify_audio_pipeline.py`, `verify_alpha_parity.py`). Filas 11–13 y PTT: validados en sesión piloto. **Auditoría CC:** `.omo/evidence/cc-audit-2026-06.md`.

## Criterios de éxito

- Frases spotter suenan en **< 500 ms** con cache caliente (segunda repetición).
- Respuestas LLM suenan tras `advice_end`; no durante `THINKING_LLM`.
- Spotter **nunca** queda bloqueado por consejo del ingeniero en cola.
- Gaps y perlas **no** saturan `/tts`.

## Gate automatizado (sin LMU)

```powershell
python scripts/verify_audio_pipeline.py
python scripts/verify_alpha_parity.py
python scripts/verify_spotter_pipeline.py
```

## MQTT E2E (broker local opcional)

```powershell
docker run -d --name vantare-mqtt -p 1883:1883 eclipse-mosquitto:2
$env:MQTT_ENABLED="true"
python scripts/verify_mqtt_e2e.py
```

## Captura opcional de trazas

```powershell
python scripts/capture_spotter_trace.py
```
