# Findings & Decisions — Fase 6-8 Cleanup

## Requirements
- T6.3: Limpiar 3 errores TS6133 (unused vars) en App.tsx, audioQueue.test.ts, configStore.test.ts
- T8.3: Añadir `advice_id` a logs de error en engine.py y llm_client.py
- T8.4: Capturar `RuntimeError` al llamar `receive()` tras desconexión WebSocket

## Research Findings

### T6.1 — Tests TTS router real
- Archivo: `backend/tests/test_tts.py` (148 líneas, 8 tests)
- Ya usa `from src.routers.tts import router` (import del router real)
- Mockea `app.state` con `make_app_with_tts_services()`
- Todos los tests pasan (8/8): `pytest tests/test_tts.py -v` → 8 passed
- **Conclusión**: T6.1 ya estaba completado

### T6.2 — Tests LLM async con VLLMClient
- Archivo: `backend/tests/test_llm_async.py` (110 líneas, 4 tests)
- Ya importa `VLLMClient` de `src.intelligence.llm_client`
- Ya mockea OpenAI SDK con `AsyncMock`
- Todos los tests pasan (4/4): `pytest tests/test_llm_async.py -v` → 4 passed
- **Conclusión**: T6.2 ya estaba completado

### T6.3 — TS6133 unused vars
- 3 errores de `tsc --noEmit`:
  1. `App.tsx:36` — `sendBinary` extraído de useWebSocket() pero nunca usado
  2. `audioQueue.test.ts:10` — `vi` importado de vitest pero no usado
  3. `configStore.test.ts:11` — `AppConfig` importado pero no usado
- Solución: eliminar cada variable no usada del destructuring/import

### T8.3 — Logging advice_id
- `engine.py`: advice_id se genera en `evaluate_triggers()` (L161), se pasa a `_run_llm_stream()` (L188)
- Líneas de log sin advice_id en engine.py:
  - L369: `logger.error(f"Error en ask_async LLM stream: {e}")` → sin advice_id
  - L379-380: error en task done callback → ya incluye `self._current_advice_id` (L380)
- `llm_client.py`: advice_id se recibe como parámetro en `ask_streaming()` (L83)
- Líneas de log sin advice_id en llm_client.py:
  - L192: `logger.error("Error en streaming LLM: %s", e)` → sin advice_id
  - L287: `logger.error(f"Error en ask_streaming_text: {e}")` → sin advice_id

### T8.4 — RuntimeError disconnect WebSocket
- Archivo: `backend/src/routers/websocket.py`
- `websocket_endpoint()` en L174: `raw = await websocket.receive()`
- Ya captura `WebSocketDisconnect` (L209)
- El RuntimeError ocurre cuando se llama `receive()` después de que el websocket ya está desconectado
- Algunas versiones de Starlette/websockets lanzan `RuntimeError` en vez de `WebSocketDisconnect`
- Solución: añadir `except RuntimeError` junto a `except WebSocketDisconnect`

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Marcar T6.1/T6.2 como ya completadas | Verificación confirmó tests pasan con implementaciones actuales |
| No modificar estructura de tests existentes | Tests ya son correctos; no necesitan refactor |
| Añadir advice_id a logs existentes sin cambiar formato | Mínima intrusión, máximo valor diagnóstico |
| Añadir RuntimeError como excepción adicional | No rompe el WebSocketDisconnect existente |
