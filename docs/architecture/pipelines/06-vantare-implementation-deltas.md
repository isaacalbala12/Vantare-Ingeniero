# Vantare — Stack e implementación (deltas vs CC)

## Propósito de este doc

Documentar **cómo está montado Vantare** y qué partes **no tienen equivalente en Crew Chief**. No son objetivo de paridad conductual; son constraints o extensiones.

**Paridad CC** = pipelines 01–05 + matriz YAML. **Este doc** = no confundir deuda de stack con diseño CC.

## Sidecar dual-process (Fase 7)

```
LMU → sidecar (Windows) ──WS──→ backend (FastAPI) ──WS──→ Tauri
```

CC: **un proceso** lee y habla.

| Efecto | Riesgo paridad |
|--------|----------------|
| Frame cada 2 s al backend | Ingeniero evalúa más lento que CC |
| Sidecar vs backend version skew | Strings sesión stale |
| Reinicio sidecar olvidado | Código viejo en pista |

**Mitigación:** `session_type_int`, health/version, evaluar voz @ 20 Hz en backend.

## `shared-strategy` (no existe en CC)

Paquete Python con cálculos deterministas:

- Fuel / tyre / brake / hybrid / pit window / competitors
- CC hace esto **dentro** de Events + lógica pit

**Rol:** alimentar **datos** al canal ingeniero; no sustituir **cuándo/cómo habla**.

Archivos: `shared-strategy/src/shared_strategy/`, `StrategyService`, `StrategyRunner`.

## Loop 0.5 Hz (`strategy_sender_loop`)

```python
# backend/src/routers/websocket.py
await asyncio.sleep(2.0)  # evaluate_cycle + strategy WS
```

**Anti-CC:** ver pipeline 03. Cálculo estrategia @ 2 s puede quedarse; **voz ingeniero no debería estar atada solo a esto**.

## CommentaryOrchestrator + LLM batch

| Componente | CC equivalente |
|------------|----------------|
| `commentary_orchestrator.py` debounce 3–8 s | **Ninguno** |
| `commentary_llm_formatter.py` | **Ninguno** |

Introducido para “narración natural” alpha — **conflicto directo** con paridad CC.

**Estado objetivo:** opt-in o eliminar como vía principal; mensajes CC → plantillas pipeline 03.

## IntelligenceEngine triggers + LLM stream

Extension Vantare para análisis. CC responde con grammar/WAV.

Migración paridad: triggers `race_only` con **salida template** donde CC no usa LLM (`PushNow`, `SessionEnd`, etc.).

## RAG / EventStore / Ticker

| Feature | CC |
|---------|-----|
| ChromaDB event store | No |
| Ticker 400 tokens | No |

Solo relevantes para **PTT**, no para spotter/ingeniero proactivo CC-like.

## UI telemetría MessagePack 20 Hz

Frontend recibe frame para overlays/dashboard — CC no tiene este pipeline (no es HUD).

Archivo: `telemetry_sender_loop` → `useWebSocket` binary handler.

## MQTT

CC: `Events/Mqtt.cs`. Vantare: `mqtt_service.py` opt-in. Pipeline publicación separado; no afecta voz.

## Bundled backend Tauri

`frontend/src-tauri/binaries/backend/_internal/` puede ir **detrás** de dev tree.

**Paridad en pista:** rebuild bundle tras cambios spotter/engineer.

## Mapa: doc pipeline → código actual

| Doc paridad | Código Vantare hoy |
|-------------|-------------------|
| 01 GameState | sidecar, websocket, session_kind |
| 02 Spotter | spotter.py @ 20 Hz |
| 03 Engineer | proactive_monitors + triggers @ 0.5 Hz + batch |
| 04 Playback | priorityAudioQueue |
| 05 Pilot | usePTT + LLM |
| 06 (este) | sidecar, shared-strategy, commentary LLM, RAG |

## Orden refactor (post-documentación)

1. Frecuencia + frame único (01)
2. Spotter lateral/FCY pause (02)
3. **Desmontar batch ingeniero** (03) — máximo impacto percepción “como CC”
4. Playback expiry (04)
5. Fast-path grammar opcional (05)

## Referencias

- `docs/superpowers/specs/2026-05-27-fase-7-sidecar-windows-design.md`
- `docs/ai/orchestrator.md` — niveles voz (legacy; priorizar esta carpeta pipelines)
- `.omo/evidence/cc-p0-wave1-locked.md`

---

*Reemplaza la función de los antiguos docs 02-strategy, 04-proactive, 05-triggers como “pipelines CC”.*
