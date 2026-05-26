# Task Plan: Fase 6-8 Cleanup — Correcciones Tests y Optimizaciones

## Goal
Completar las 4 tareas restantes de Fase 6 y Fase 8: limpiar variables TS no usadas (T6.3), añadir advice_id al logging (T8.3), silenciar error de desconexión WebSocket (T8.4). Las tareas T6.1 y T6.2 (tests TTS y LLM) ya estaban hechas.

## Current Phase
Phase 1

## Phases

### Phase 1: Análisis y Verificación de Estado Actual
- [x] Verificar estado de T6.1 (tests TTS con router real) — 8 tests pasan, ya migrados al router real ✅
- [x] Verificar estado de T6.2 (test_llm_async con VLLMClient) — 4 tests pasan, ya migrados ✅
- [x] Identificar TS6133 restantes (3 errores)
- [x] Mapear puntos donde falta advice_id en logs de engine.py y llm_client.py
- [x] Localizar el punto de desconexión en websocket.py
- **Status:** complete

### Phase 2: T6.3 — Limpiar TS6133 unused vars (Frontend)
- [ ] Eliminar `sendBinary` de App.tsx línea 36
- [ ] Eliminar `vi` de audioQueue.test.ts línea 10
- [ ] Eliminar `AppConfig` de configStore.test.ts línea 11
- [ ] Verificar `npx tsc --noEmit` = 0 errores
- **Status:** pending

### Phase 3: T8.3 — Logging con advice_id (Backend)
- [ ] Añadir `advice_id` a logs de error en `engine.py` (_run_llm_stream, _on_llm_task_done)
- [ ] Añadir `advice_id` al log de error en `llm_client.py` (ask_streaming, ask_streaming_text)
- [ ] Verificar que pytest backend sigue pasando
- **Status:** pending

### Phase 4: T8.4 — Silenciar RuntimeError de desconexión WebSocket
- [ ] Añadir captura de `RuntimeError` en `websocket_endpoint` para el caso `websocket.receive()` post-disconnect
- [ ] Verificar que el backend arranca sin errores
- **Status:** pending

### Phase 5: Verificación Final
- [ ] `npx tsc --noEmit` = 0 errores
- [ ] `npx vitest run` = 42 tests pasan
- [ ] `pytest backend/tests/` = todos pasan
- [ ] Backend arranca sin errores
- [ ] Actualizar orchestrator.md
- **Status:** pending

## Key Questions
1. ~~¿T6.1 y T6.2 ya están completas?~~ → Sí, verificadas. Tests usan router real y VLLMClient.
2. ¿Dónde exactamente añadir advice_id en los logs? → Líneas de error en engine.py y llm_client.py
3. ¿Qué versión de Starlette causa RuntimeError en receive() post-disconnect? → Se captura con `except RuntimeError`

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| T6.1 y T6.2 marcadas como ya completadas | Tests existentes ya pasan con router real y VLLMClient |
| Saltar a Fase 2 (Sidecar) tras este cleanup | Las tareas restantes (T6.1-T6.2) ya estaban hechas; solo quedan 4 tareas triviales |
| Usar `except RuntimeError` además de `WebSocketDisconnect` | Algunas versiones de websockets lanzan RuntimeError en receive() post-disconnect |

## Notes
- T6.1 y T6.2 verificadas: 8/8 tests TTS + 4/4 tests LLM pasan con implementaciones actuales
- 3 errores TS6133 triviales (variables no usadas)
- advice_id ya se genera y pasa entre engine y llm_client, solo falta en los loggers
- websocket.py ya tiene try/except para WebSocketDisconnect, falta RuntimeError para edge case
