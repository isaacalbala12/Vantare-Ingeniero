# Quality Analysis & Corrections — Plan de Acción

**Goal:** Corregir todos los hallazgos de seguridad, calidad, cobertura de tests y Rust para declarar la fase alpha completada.

**Criterio de éxito:** 
- 0 CRITICAL/HIGH en seguridad
- Backend coverage ≥70%
- Frontend coverage ≥60%
- Rust: 0 unwrap críticos, CSP configurado
- Todos los tests pasando

**Regla OBLIGATORIA por fase:** Cada cambio debe ir acompañado de tests de regresión que verifiquen que el comportamiento no cambia. Para cada archivo modificado, debe existir un test que:
1. Capture el comportamiento ANTES del cambio (si no existe test, crearlo primero)
2. Aplique el cambio
3. Verifique que el test SIGUE PASANDO (regresión)
4. Añada tests NUEVOS para la funcionalidad corregida si no existían

---

## Fase 1: 🔒 Correcciones de Seguridad (Prioridad CRÍTICA)

### 1.1 Eliminar `.env` del tracking de git
- **Archivos:** `.gitignore`, `backend/.gitignore`
- **Tests de regresión:**
  - ✅ Verificar que `git ls-files backend/.env` ya no aparece
  - ✅ Verificar que `backend/.env` está listado en `.gitignore`
  - ✅ Verificar que `backend/.env.example` existe (si no, crearlo)
- **Acción:** `git rm --cached backend/.env`, crear `.env.example`, añadir `backend/.env` a `.gitignore`
- **Riesgo:** Clave API expuesta si el repo se filtra

### 1.2 Restringir CORS a orígenes específicos
- **Archivo:** `backend/src/main.py:260-271`
- **Tests de regresión:**
  - ✅ Test existente de health endpoint debe seguir pasando (test_health.py)
  - ✅ Nuevo test: verificar que OPTIONS request con origen válido recibe CORS headers correctos
  - ✅ Nuevo test: verificar que OPTIONS request con origen inválido es rechazado
  - ✅ Nuevo test: verificar que `allow_methods` ya no incluye `*`
- **Acción:** Cambiar `allow_methods=["*"]` → `["GET", "POST"]`, usar `settings.FRONTEND_ORIGIN`

### 1.3 Configurar CSP en Tauri
- **Archivo:** `frontend/src-tauri/tauri.conf.json`
- **Tests de regresión:**
  - ✅ Verificar que `tauri.conf.json` sigue siendo JSON válido
  - ✅ Verificar que la app sigue compilando con `cargo check` (Windows)
  - ✅ Nuevo test: verificar que `csp` ya no es `null`
- **Acción:** Establecer `csp` con política mínima

### 1.4 Reducir permisos shell en Tauri
- **Archivo:** `frontend/src-tauri/capabilities/default.json`
- **Tests de regresión:**
  - ✅ Verificar que JSON sigue siendo válido
  - ✅ Nuevo test: verificar que `shell:allow-execute` NO está en permisos
  - ✅ Verificar que `shell:allow-spawn` SÍ está en permisos
- **Acción:** Eliminar `shell:allow-execute`, mantener solo `shell:allow-spawn`

### 1.5 Fix `default_window_icon().unwrap()` en Rust
- **Archivo:** `frontend/src-tauri/src/main.rs:155`
- **Tests de regresión:**
  - ✅ Verificar que el código compila (cargo check)
  - ✅ Nuevo test: verificar que ya no hay `.unwrap()` en esa línea (grep)
  - ✅ Nuevo test: verificar que hay manejo de `None` (unwrap_or_else / if let Some)
- **Acción:** Cambiar `.unwrap()` → `.unwrap_or_else()` con fallback

### 1.6 Añadir logging a try-except-pass silenciosos
- **Archivos:** `engine.py`, `spotter.py`
- **Tests de regresión:**
  - ✅ Tests existentes de engine deben seguir pasando
  - ✅ Tests existentes de spotter deben seguir pasando
  - ✅ Nuevo test: verificar que `except: pass` ya no existe en los archivos modificados
  - ✅ Nuevo test: mockear logger y verificar que se llama `logger.warning()` en los casos de error
- **Riesgo:** Errores silenciados sin diagnóstico

---

## Fase 2: 🧹 Calidad de Código (Prioridad ALTA)

### 2.1 Ruff auto-fix imports muertos
- **Archivos:** 16 imports en múltiples archivos
- **Tests de regresión:**
  - ✅ Test suite completa debe pasar (pytest)
  - ✅ TypeScript debe compilar (tsc --noEmit)
  - ✅ Nuevo test: verificar que `ruff check src/ --select F401` da 0 errores
- **Acción:** `ruff check src/ --select F401,F841 --fix`

### 2.2 Fix `google` undefined en gemini_tts_service.py
- **Archivo:** `backend/src/services/gemini_tts_service.py:32`
- **Tests de regresión:**
  - ✅ Test existente de TTS debe seguir pasando (test_tts.py)
  - ✅ Nuevo test: importar gemini_tts_service sin GEMINI_API_KEY → no debe crashear
  - ✅ Nuevo test: importar gemini_tts_service SIN google.genai instalado → no debe crashear
- **Acción:** Añadir import condicional con try/except

### 2.3 Ruff auto-fix resto de errores
- **Archivos:** E402, F811
- **Tests de regresión:**
  - ✅ Test suite completa debe pasar
  - ✅ Nuevo test: `ruff check src/` da 0 errores
- **Acción:** `ruff check src/ --fix`

---

## Fase 3: 🧪 Tests Backend (Prioridad ALTA)

**Regla especial:** Para cada módulo, PRIMERO escribir test que documente el comportamiento actual (aunque falle por falta de mocks), LUEGO escribir el código si es necesario.

### 3.1 Tests para engine.py
- **Cobertura actual:** 0%
- **Tests a crear:** `tests/test_engine.py`
- **Tests de regresión para el workflow:**
  - ✅ `test_evaluate_cycle_with_trigger()` — Llama evaluate_cycle con trigger simulado, verifica que se envía LLMPendingMessage
  - ✅ `test_evaluate_cycle_no_trigger()` — Llama evaluate_cycle sin trigger, verifica que NO se envía nada
  - ✅ `test_handle_pilot_question()` — Simula pregunta de piloto, verifica que se procesa
  - ✅ `test_cancel_current_llm()` — Cancela LLM en curso, verifica que se envía AdviceEndMessage de interrupción
  - ✅ `test_ask_async()` — Llama ask_async, verifica que devuelve tokens
  - ✅ `test_preemption_higher_priority()` — Trigger de alta prioridad interrumpe uno de baja

### 3.2 Tests para live_context.py
- **Cobertura actual:** 0%
- **Tests a crear:** Ampliar `tests/test_live_context.py`
- **Tests de regresión para el workflow:**
  - ✅ `test_on_lap_completed_updates_pace_buffer()` — Al completar vuelta, el buffer de ritmo se actualiza
  - ✅ `test_on_lap_completed_updates_wear_buffer()` — Al completar vuelta, el buffer de desgaste se actualiza
  - ✅ `test_update_realtime()` — Datos en tiempo real se actualizan sin completar vuelta
  - ✅ `test_snapshot_contains_expected_fields()` — El snapshot tiene todos los campos requeridos
  - ✅ `test_multiple_laps_tracked()` — Múltiples vueltas se acumulan correctamente

### 3.3 Tests para llm_client.py
- **Cobertura actual:** 0%
- **Tests a crear:** Ampliar `tests/test_llm_client_advanced.py`
- **Tests de regresión para el workflow:**
  - ✅ `test_ask_streaming_text_returns_tokens()` — Texto plano: verificar que devuelve tokens uno a uno
  - ✅ `test_ask_streaming_with_tool_calls()` — Streaming con tool calls: verificar que se parsean correctamente
  - ✅ `test_health_check_returns_true()` — Health check con servidor mock devuelve True
  - ✅ `test_health_check_returns_false()` — Health check con servidor caído devuelve False
  - ✅ `test_streaming_cancellation()` — Cancelación: verificar que se lanza CancelledError
  - ✅ `test_streaming_timeout()` — Timeout: verificar que se maneja gracefulmente

### 3.4 Tests para strategy_service.py
- **Cobertura actual:** 0%
- **Tests a crear:** `tests/test_strategy_service.py`
- **Tests de regresión para el workflow:**
  - ✅ `test_process_cycle_with_valid_telemetry()` — Ciclo completo con telemetría válida
  - ✅ `test_process_cycle_with_partial_data()` — Ciclo con datos parciales (sin crashear)
  - ✅ `test_get_latest_advice_returns_advice()` — Devuelve el último consejo generado
  - ✅ `test_get_latest_advice_no_data()` — Sin datos, devuelve None
  - ✅ `test_get_race_summary()` — Resumen de carrera con datos simulados
  - ✅ `test_process_cycle_does_not_block()` — Verificar que no bloquea el event loop

### 3.5 Tests para websocket.py
- **Cobertura actual:** 0%
- **Tests a crear:** Ampliar `tests/test_ws_integration.py`
- **Tests de regresión para el workflow:**
  - ✅ `test_websocket_connect_disconnect()` — Conectar y desconectar sin errores
  - ✅ `test_websocket_receive_telemetry()` — Enviar telemetría y verificar que se recibe
  - ✅ `test_websocket_receive_strategy()` — Verificar que se reciben frames de estrategia
  - ✅ `test_websocket_pilot_question()` — Enviar pregunta de piloto, verificar que se procesa
  - ✅ `test_websocket_reconnect()` — Desconectar y reconectar, verificar que funciona
  - ✅ `test_websocket_multiple_clients()` — Múltiples clientes simultáneos
  - ✅ `test_websocket_invalid_message()` — Mensaje inválido no crashea el servidor

---

## Fase 4: 🔵 Tests Frontend (Prioridad MEDIA)

### 4.1 Tests para appStore.ts
- **Estado:** Sin test
- **Tests a crear:** `src/__tests__/appStore.test.ts`
- **Tests de regresión para el workflow:**
  - ✅ `test_initial_state()` — Estado inicial correcto
  - ✅ `test_setRadioMode_updates_mode()` — Cambiar modo radio
  - ✅ `test_updateTelemetry()` — Actualizar telemetría
  - ✅ `test_triggerAlert()` — Disparar alerta
  - ✅ `test_dismissAlert()` — Descartar alerta
  - ✅ `test_addMessageToHistory()` — Añadir mensaje al historial
  - ✅ `test_setLatestAdvice()` — Establecer último consejo
  - ✅ `test_setLatestAlert()` — Establecer última alerta

### 4.2 Tests para useWebSocket.ts
- **Estado:** Sin test
- **Tests a crear:** `src/__tests__/useWebSocket.test.ts`
- **Mock necesario:** `global.WebSocket`, `global.fetch`
- **Tests de regresión para el workflow:**
  - ✅ `test_connect_creates_websocket()` — Al conectar, se crea WebSocket con URL correcta
  - ✅ `test_onmessage_telemetry()` — Al recibir mensaje telemetry, actualiza estado
  - ✅ `test_onmessage_alert_with_preloaded()` — Alerta con pregrabado usa audioQueue.enqueue con isLocalFile=true
  - ✅ `test_onmessage_alert_without_preloaded()` — Alerta sin pregrabado usa TTS queue
  - ✅ `test_onmessage_advice_tokens()` — Tokens de consejo se acumulan
  - ✅ `test_onmessage_state_snapshot()` — State snapshot restaura radio_mode y latest_advice
  - ✅ `test_reconnect_on_close()` — Al cerrarse, programa reconexión
  - ✅ `test_sendJson()` — Enviar JSON formatea correctamente

### 4.3 Tests para api.ts
- **Estado:** Sin test
- **Tests a crear:** `src/__tests__/api.test.ts`
- **Mock necesario:** `global.fetch`
- **Tests de regresión para el workflow:**
  - ✅ `test_getHealth_returns_data()` — /health devuelve estructura correcta
  - ✅ `test_getHealth_timeout()` — Timeout de 5s se respeta
  - ✅ `test_getHealth_http_error()` — Error HTTP maneja gracefulmente
  - ✅ `test_getHistory_returns_records()` — /history devuelve array
  - ✅ `test_getHistory_empty()` — /history vacío devuelve []
  - ✅ `test_getBaseUrl()` — URL base se construye correctamente desde IP/puerto

---

## Fase 5: 🦀 Rust (Prioridad MEDIA)

### 5.1 Fix unwrap en default_window_icon
- **Archivo:** `main.rs:155`
- **Tests de regresión:**
  - ✅ `grep '\.unwrap()' main.rs` ya no muestra línea 155
  - ✅ `cargo check` compila (Windows)

### 5.2 Agregar timeout con backoff al health check
- **Archivo:** `main.rs:126-145`
- **Tests de regresión:**
  - ✅ El health check sigue funcionando (verificar en runtime)
  - ✅ Nuevo test (revisión de código): verificar que hay backoff 5s→10s→20s→max 60s
- **Acción:** Backoff exponencial en vez de intervalo fijo

### 5.3 Validar existencia de sidecars antes de spawn
- **Archivo:** `main.rs:35-123`
- **Tests de regresión:**
  - ✅ El spawn de sidecars sigue funcionando cuando el binario existe
  - ✅ Nuevo test (revisión de código): verificar que hay chequeo de existencia antes de spawn

---

## Fase 6: ✅ Verificación Final

### 6.1 Test de integración: workflow completo backend
- ✅ Arrancar app con datos simulados
- ✅ Enviar telemetría vía WebSocket
- ✅ Verificar que el engine procesa triggers
- ✅ Verificar que el spotter genera alertas
- ✅ Verificar que el strategy service calcula
- ✅ Verificar que los mensajes llegan al cliente WebSocket

### 6.2 Ejecutar test suite backend completa
- Comando: `pytest --cov=src/ --cov-fail-under=70`

### 6.3 Ejecutar test suite frontend
- Comando: `npx vitest run`

### 6.4 Verificar TypeScript
- Comando: `npx tsc --noEmit`

### 6.5 Verificar Rust compila
- Comando: `cargo check` (en Windows)

### 6.6 Actualizar orchestrator.md
- Marcar alpha completada

---

## Errores Conocidos

| Error | Contexto | Resolución |
|-------|----------|------------|
| `google.genai` NameError | gemini_tts_service.py:32 | Fix en Fase 2.2 |
| `DeprecationWarning: _pack_` | lmu_data.py:412-464 | Migrar a `_layout_ = 'ms'` en Python 3.19+ |
| `CSP: null` | tauri.conf.json | Fix en Fase 1.3 |
| `shell:allow-execute` | capabilities/default.json | Fix en Fase 1.4 |
