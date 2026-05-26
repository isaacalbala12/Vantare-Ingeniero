# 🏎️ Vantare Ingeniero IA — Orquestador de Proyecto

## Estado actual (26 mayo 2026)

### LLM: ✅ Cadena completa funcional

| Componente | Puerto | Estado | Notas |
|-----------|--------|--------|-------|
| **Hipfire** (Qwen 3.5 4B) | `:11435` | ✅ `hipfire serve` | Usa puerto 11435 por defecto |
| **LiteLLM** (proxy) | `:4000` | ✅ Config YAML | Expone modelo como `hipfire-qwen` |
| **Cloudflare Tunnel** | — | ✅ Activo | URL cambia cada reinicio |
| **Backend (FastAPI)** | `:8008` | ✅ LLM responde vía `/ask` | `.env` con tunnel URL + `/v1` |

### Servicios backend
- Telemetría LMU: ✅ TelemetryReader offline (simulado), esperando frontend real
- Estrategia: ✅ StrategyService loop 2s activo, cálculos con datos simulados
- Spotter: ✅ 20Hz, 8 alertas deterministas, bypass LLM
- TTS: ✅ Edge (OK) + Piper (OK) + ElevenLabs (NO) + Gemini (NO)
- LLM Client: ✅ configurado con `hipfire-qwen` → Tunnel → LiteLLM → Hipfire

### Estado del frontend (React/TypeScript/Tauri)
- ✅ 42 tests unitarios pasan (Vitest)
- ⚠️ 15 errores TypeScript (12 son TS6133 unused vars, 3 reales en `usePTT.ts`)
- ❌ PTT no funcional (errores de tipo en `usePTT.ts`)
- ❌ WebSocket telemetría backend←frontend no implementada

---

## Lecciones Aprendidas — Infraestructura LLM

| Síntoma | Causa | Solución |
|---------|-------|----------|
| `"No connected db."` | 2 instancias LiteLLM peleando puerto 4000 | Matar todas, reiniciar con `--config` |
| `"LLM Provider NOT provided"` | Faltaba prefijo `openai/` en modelo | `model: openai/qwen3.5-4b.mq4` |
| `"Missing credentials"` | Provider openai requiere api_key | `api_key: sk-vantare-ingeniero-v2` en config |
| `"Connection error"` | api_base apuntaba a puerto 8000 (Hipfire usa 11435) | `http://localhost:11435/v1` |
| Hipfire no arranca con `nohup` | nohup rompe procesos con TTY | Usar `&` directamente |
| LiteLLM `Exit 127` | litellm no está en PATH global | Activar virtualenv primero |
| **Regla clave** | Hipfire usa puerto 11435 por defecto | Configurar LiteLLM para 11435 |

---

## Comandos Verificados

### PC Linux LLM

#### Hipfire
```bash
hipfire serve &
curl -s http://localhost:11435/v1/models
```

#### LiteLLM
```bash
source ~/litellm_env/bin/activate

cat > ~/litellm_config.yaml << 'EOF'
model_list:
  - model_name: hipfire-qwen
    litellm_params:
      model: openai/qwen3.5-4b.mq4
      api_base: http://localhost:11435/v1
      api_key: sk-vantare-ingeniero-v2
EOF

litellm --config ~/litellm_config.yaml --port 4000 > /tmp/litellm.log 2>&1 &
curl -s http://localhost:4000/v1/models
```

#### Cloudflare Tunnel (ad-hoc, sin config)
```bash
cloudflared tunnel --url http://localhost:4000
# Aparece URL tipo https://xxxx.trycloudflare.com → copiarla
```

### PC Backend (esta máquina)

#### Arrancar backend
```bash
cd /home/isaac-albala/Vantare-Ingeniero/backend
.venv/bin/python run_dev.py
# Escucha en http://127.0.0.1:8008
```

#### Probar LLM
```bash
curl -s http://127.0.0.1:8008/ask -H "Content-Type: application/json" -d '{"question": "Di OK"}'
```

#### Tests
```bash
# Backend (100 tests)
cd backend && .venv/bin/python -m pytest -v

# Frontend (42 tests)
cd frontend && npx vitest run
```

### URL actual del túnel
**Actual**: `https://sunny-longer-cube-ruling.trycloudflare.com`
**En `.env`**: `LLM_BASE_URL=https://sunny-longer-cube-ruling.trycloudflare.com/v1`
**Cuando cambie**: copiar nueva URL de terminal cloudflared → editar `.env` → reiniciar backend

---

## Arquitectura

```
┌─ Windows (Tauri/React + LMU) ──────────────────────────────────┐
│                                                                 │
│  LMU Shared Memory ─→ TelemetryReader (20Hz, real)              │
│                        │                                        │
│                        ├→ SpotterService (20Hz, 8 alertas)     │
│                        │    → TTS directo, bypass LLM          │
│                        │                                        │
│                        ├→ StateChangeDetector (Fase 1)          │
│                        │    → Eventos + snapshots               │
│                        │    → WebSocket al backend              │
│                        │                                        │
│                        └→ WebSocket 20Hz → Backend (FASE 0)    │
│                             (telemetría real para estrategia)    │
│                                                                 │
│  PTT (Push-To-Talk) ─→ WebSocket pila pregunta ──────────────┐ │
│  TTS audio ←── playback cola ←── WebSocket advice_* ◄───────┐│ │
└─────────────────────────────────────────────────────────────┘││ │
                                                               ││ │
┌─ Linux (FastAPI + LLM) ─────────────────────────────────────┐││ │
│                                                              ▼▼ ▼
│  WebSocket handler (websocket.py)                            ││ │
│    ├→ telemetry event (FASE 0) → latest_client_frame         │ │
│    ├→ pilot_question → IntelligenceEngine                    │ │
│    ├→ strategy_frame (FASE 1) → strategy_service.update()    │ │
│    └→ advice streaming → advice_token / advice_end          │ │
│                                                              │ │
│  StrategyService ─→ Fuel/Tyre/Brake/Hybrid/PitWindow calc    │ │
│    └→ get_latest_advice() para WebSocket loop (2s)           │ │
│                                                              │ │
│  IntelligenceEngine (0.5s triggers + pilot questions)         │ │
│    ├→ 12 triggers automáticos                                │ │
│    ├→ PilotQuestionTrigger (PP alta)                         │ │
│    └→ VLLMClient (OpenAI SDK) ─→ Cloudflare Tunnel           │ │
│                                   └→ LiteLLM :4000            │ │
│                                      └→ Hipfire :11435        │ │
│                                         └→ Qwen 3.5 4B       │ │
│                                                              │ │
│  RAG (FASE 2): ChromaDB + multilingual-e5-large              │ │
│    └→ Historial de eventos + snapshots por vuelta             │ │
│                                                              │ │
│  Ticker (FASE 3): formato compacto para prompts              │ │
│    └→ DRV|TYR|BRK|GAP|SES|WTH|RIV en ~400 tokens             │ │
│                                                              │ │
│  Transporte (FASE 4): MessagePack + Delta encoding            │ │
│    └→ 20-50 bytes por frame delta, snapshot 5s cada 30       │ │
└──────────────────────────────────────────────────────────────┘ │
                                                               │ │
┌─ PC LLM (Linux, GPU) ───────────────────────────────────────┘ │
│  Hipfire :11435 ←── LiteLLM :4000 ←── Cloudflare Tunnel ──────┘
│  (Qwen 3.5 4B, Vulkan, RX 6600 XT 8GB)
└────────────────────────────────────────────────────────────────
```

---

## 🗺️ Roadmap Completo — Todas las Fases Detalladas

### Fase 0: WebSocket Telemetría (F0) — CRÍTICO
**Objetivo**: Que el frontend Windows envíe telemetría real al backend Linux para estrategias reales.

#### ¿Por qué?
El backend Linux no tiene acceso a la shared memory de LMU. Usa `TelemetryReader(offline=True)` que genera datos simulados. El StrategyService calcula estrategia (combustible, neumáticos, pits) con datos falsos. Hasta que no reciba telemetría real, todo lo que haga el LLM es sobre datos inventados.

#### Tareas concretas

**T0.1: Handler `telemetry` en websocket.py**
- El backend ya recibe WebSocket del frontend
- Falta un `if event == "telemetry": app_state.latest_client_frame = data`
- Ya está el health check que reporta `frontend_telemetry.received`
- Archivo: `backend/src/routers/websocket.py` (~línea 183)

**T0.2: Strategy loop use latest_client_frame**
- `strategy_sender_loop` usa `reader.get_state()` (simulado)
- Cambiar a: intentar `latest_client_frame` primero, fallback a reader
- Archivo: `backend/src/routers/websocket.py` (~línea 105)

**T0.3: Inicializar latest_client_frame en main.py**
- `app.state.latest_client_frame = None`
- Cambiar `TelemetryReader(offline=True)` explícitamente
- Archivo: `backend/src/main.py` (~línea 59)
- ✅ YA IMPLEMENTADO (lo verificamos antes)

**T0.4: Frontend enviar telemetría a 20Hz**
- `useWebSocket.ts`: añadir `useEffect` con `setInterval(sendJson("telemetry", lastTelemetry), 50)`
- Archivo: `frontend/src/hooks/useWebSocket.ts`
- ⚠️ Antes de esto hay que arreglar los errores TypeScript de `usePTT.ts`

**T0.5: Test de integración WebSocket**
- Script Python que envía telemetría simulada y verifica `health`
- Verificar que `frontend_telemetry.received: true`

**Dependencias**: ❌ Ninguna directa, pero el PTT/captura de telemetría del frontend necesita que `usePTT.ts` compile.

**Orden**: F0.1 → F0.2 → F0.4 → F0.5 (F0.3 ya hecho)

---

### Fase 0b: Reparar errores TypeScript del frontend — CRÍTICO
**Objetivo**: Que el frontend compile sin errores para poder desarrollar.

#### ¿Por qué?
Hay 3 errores reales en `usePTT.ts` que impiden el funcionamiento del PTT:
1. Línea 78: `await` fuera de función `async` — la llamada a `sendBinary` está mal ubicada
2. Línea 89: `Uint8Array` no es `ArrayBuffer|Blob` — error de tipo en `sendBinary()`
3. Línea 99: `Expected 0 arguments, got 1` — función llamada con argumento que no acepta

Además, 12 errores TS6133 (variables declaradas pero no usadas) que no rompen la compilación pero ensucian.

**Archivo**: `frontend/src/hooks/usePTT.ts`

**Dependencias**: ❌ Ninguna. Se puede hacer ahora mismo.

---

### Fase 1: Correcciones Robustez — bugs conocidos
**Objetivo**: Arreglar bugs identificados en planes anteriores que degradan la experiencia.

#### 1.1 Fallback WAV cuando SpeechRecognition no disponible
- **Archivo**: `frontend/src/App.tsx` (handlePTTEnd)
- **Qué**: Si `webkitSpeechRecognition` falla (WebView2 en Tauri), enviar WAV al backend para transcripción ASR
- **Endpoint nuevo**: `POST /transcribe` en backend (por ahora devuelve texto vacío, placeholder para Whisper)
- **Prioridad**: Alta

#### 1.2 Unificar puerto a 8008
- **Archivos**: `backend/src/config.py` (PORT default 8008), `backend/run_dev.py` (usar `settings.PORT`)
- **Estado**: Ya está en 8008 en `.env`, verificar que `config.py` también tenga 8008
- **Prioridad**: Media

#### 1.3 Cola TTS para múltiples advice_end rápidos
- **Archivo**: `frontend/src/hooks/useWebSocket.ts`
- **Qué**: Reemplazar `isTtsRequestedRef` (booleano) por cola FIFO
- **Por qué**: Si trigger automático + pregunta piloto llegan juntos, solo el primero genera TTS
- **Prioridad**: Media

#### 1.4 Timeout en llamadas HTTP del frontend
- **Archivo**: `frontend/src/App.tsx`, `frontend/src/services/api.ts`
- **Qué**: Añadir `AbortController` con timeout 15s a `/ask` y 5s a `/health`
- **Prioridad**: Alta (evita UI congelada si backend cuelga)

#### 1.5 Timeout en VLLMClient
- **Archivo**: `backend/src/intelligence/llm_client.py`
- **Qué**: Añadir `timeout=httpx.Timeout(25.0, connect=10.0, read=20.0)` al SDK OpenAI
- **Prioridad**: Alta (evita tareas bloqueadas para siempre)

#### 1.6 Selectores finos en Zustand (rendimiento)
- **Archivo**: `frontend/src/components/RadioOverlay.tsx`
- **Qué**: Suscribirse a slices individuales en vez de todo el store
- **Por qué**: Sin esto, el overlay se re-renderiza cada 50ms con cada frame de telemetría
- **Prioridad**: Media

#### 1.7 Pausar engine sin clientes conectados
- **Archivo**: `backend/src/routers/websocket.py` (strategy_sender_loop)
- **Qué**: Saltar ciclo si `manager.active_connections` está vacío
- **Prioridad**: Media (ahorra llamadas LLM innecesarias)

#### 1.8 Validación de configuración (IP/puerto/hotkey)
- **Archivo**: `frontend/src/components/ConfigPanel.tsx`
- **Qué**: Validar IP, puerto (1-65535) y hotkey (Ctrl+Shift+X) antes de guardar
- **Prioridad**: Baja

#### 1.9 AlertMessage con campos Pydantic correctos
- **Archivo**: `backend/src/models/messages.py`, `backend/src/intelligence/spotter.py`
- **Qué**: Añadir `severity`, `ttl`, `dismissable` al modelo Pydantic, eliminar `object.__setattr__`
- **Prioridad**: Media (evita pérdida de campos al serializar)

#### 1.10 Eliminar migración forzosa a hotkey "P"
- **Archivo**: `frontend/src/store/config.ts`
- **Qué**: No sobrescribir hotkey guardada del usuario
- **Prioridad**: Baja

---

### Fase 2: Sidecar StrategyService en Windows
**Objetivo**: Mover el cálculo de estrategia a Windows (donde está la shared memory real).

#### ¿Por qué?
Actualmente el StrategyService corre en Linux con datos simulados. Aunque la Fase 0 resuelva el envío de telemetría, la latencia (100ms ida+vuelta) y la fiabilidad (WebSocket puede perder frames) hacen mejor tener el motor determinista local en Windows.

#### Arquitectura del sidecar
```
Windows:
  shared-telemetry (real, 20Hz)
    └→ StateChangeDetector
         ├→ detecta: posición, pits, gap, SC, clima, degradación
         └→ genera: eventos + snapshots por vuelta
    └→ StrategyService (fuel, tyres, brakes, hybrid, pit_window, stints)
         └→ get_latest_advice()
    
    WebSocket cliente → envía al backend Linux:
      - strategy_frame → resultados de estrategia
      - ticker_update → snapshot compacto
      - events → eventos detectados
```

#### Tareas concretas

**T2.1: Crear directorio `sidecar/`**
- Nuevo proyecto Python con `shared-telemetry` y `shared-strategy` como dependencias
- `main.py` como entrypoint (WebSocket cliente, loop 20Hz)
- `requirements.txt` con websockets, shared-telemetry, shared-strategy

**T2.2: StateChangeDetector (`event_detector.py`)**
- Clase que compara frames consecutivos de telemetría
- Detecta cambios en: posición, pits (entrada/salida), gap con rival, safety car, clima, degradación
- Emite eventos con timestamp, tipo, datos relevantes
- Por vuelta: snapshot completo de ritmo, desgaste, temperaturas, gaps

**T2.3: StrategyService en sidecar**
- Copiar lógica de `shared-strategy` al sidecar
- Calcular fuel/tyres/brakes/hybrid/pit_window en tiempo real
- Enviar resultados al backend cada 2s vía WebSocket

**T2.4: Handler `strategy_frame` en websocket.py**
- El backend Linux recibe los resultados del sidecar
- `app_state.latest_strategy = strategy_data`
- Eliminar `StrategyService(reader)` del backend Linux

**T2.5: Tauri sidecar (futuro, Fase 5)**
- Empaquetar sidecar Python como binario (PyInstaller)
- Tauri lo gestiona: arrancar/parar junto con la app
- Comunicación: WebSocket localhost

**Dependencias**: Fase 0 (telemetría WebSocket) debe estar estable primero.

---

### Fase 3: RAG — Historial de Carrera
**Objetivo**: Dar al LLM contexto histórico de la carrera (eventos pasados, ritmo rivales, degradación).

#### ¿Por qué?
El LLM actual solo ve el frame actual de telemetría. No sabe lo que pasó hace 10 vueltas, si un rival está en estrategia diferente, o cómo evoluciona la degradación. Con RAG, el prompt incluye los eventos relevantes más cercanos semánticamente a la pregunta/trigger actual.

#### Stack
- **Vector DB**: ChromaDB (simple, sin servidor, persistencia en disco)
- **Embedding model**: `multilingual-e5-large` (2.2 GB RAM, CPU, ~40ms por embedding)
- **Idioma**: español + inglés (modelo multilingüe)

#### Tareas concretas

**T3.1: Instalar ChromaDB + sentence-transformers**
```bash
pip install chromadb sentence-transformers
```
Descargar `multilingual-e5-large` (2.2 GB, cacheado en HF)

**T3.2: EventStore (`backend/src/persistence/event_store.py`)**
- Clase que gestiona ChromaDB
- `store_event(event_type, data, metadata)` → inserta en colección
- `query(query_text, top_k=5)` → búsqueda semántica
- `store_snapshot(lap, driver, snapshot_data)` → por vuelta
- `get_snapshots(driver=None, lap_range=None)` → recuperar históricos

**T3.3: LiveContextManager — extensiones**
- Guardar snapshots históricos por vuelta por driver
- Timeline de eventos para el prompt
- Buffers de ritmo: últimas 5 vueltas, top-10 rivales
- Buffers de desgaste: últimas 5 vueltas propias
- Exponer método `get_context_for_prompt(query, current_frame)` → RAG top-5 + buffers

**T3.4: Integrar RAG en context_builder.py**
- Al construir prompt para LLM, añadir top-5 eventos históricos
- Formato: `## RECORDATORIO HISTÓRICO\n- V10: Safety Car desplegado\n- V15: Boxes ALO\nduró 35s\n...`
- Límite: ~100 tokens de RAG por prompt

**Dependencias**: Sidecar (Fase 2) debe estar generando eventos/snapshots para que RAG tenga datos.

---

### Fase 4: Ticker Compacto + Prompt Builder
**Objetivo**: Reducir el tamaño del prompt del LLM (~700-800 tokens total) para velocidad y economía.

#### ¿Por qué?
El prompt actual incluye telemetría como JSON verboso (~2 KB). A 0.5Hz con 500 tokens de salida, el overhead es grande. Un ticker compacto reduce a ~400 tokens la información de 40 rivales.

#### Formato ticker
```
DRV:P3|L26|F:42.3L/3.2(13L)|TYR:72/68/65/63·92/94/98/96
BRK:38/35/22/20
GAP>VST:+2.1·1:48.2|<ALO:-1.2·1:47.9·d-0.3
SES:WEC|RACE|38L|45:22
WTH:PC|22°|R30%+15m|GRN|SC:N
RIV:VST|HY|+2.1|V22|78·ALO|HY|-1.2|--|65·LEC|HY|-5.4|V22|70·...
```

**Campos**: DRV (posición, vuelta, combustible, neumáticos), BRK (frenos), GAP (gaps), SES (sesión), WTH (clima), RIV (rivales compactos, 40 máximo)

#### Tareas concretas

**T4.1: `backend/src/intelligence/ticker.py`** (nuevo)
- Función `generate_ticker(frame: TelemetryFrame) -> str`
- Formatear DRV, TYR, BRK, GAP, SES, WTH, RIV
- 40 rivales en tabla compacta (70 chars cada 2)

**T4.2: Detector de tokens**
- `tiktoken` para contar tokens del prompt antes de enviar
- Si prompt > 500 tokens: no llamar al LLM, reproducir audio pregrabado
- `"Un momento, déjame consultarlo..."`

**T4.3: Refactorizar context_builder.py**
- Usar ticker en vez de JSON de telemetría
- Incluir RAG top-5 (Fase 3) como bloque opcional
- Incluir system prompt (~200 tokens)
- Prompt total: ~700-800 tokens

**T4.4: Actualizar prompt_templates.py**
- Enseñar al LLM el formato ticker en SYSTEM_PROMPT
- Reglas de parseo y qué significa cada campo

#### Flujo final del prompt (Fase 3 + 4)
```
System: ~200 tokens (instrucciones + formato ticker)
┌────────────────────────────────────────────┐
│ Ticker compacto: ~400 tokens              │
│ DRV:P3|L26|F:42.3L/3.2(13L)|...           │
│ BRK:38/35/22/20                            │
│ GAP>VST:+2.1|<ALO:-1.2         │
│ SES:WEC|RACE|38L|45:22                    │
│ WTH:PC|22°|R30%+15m|GRN|SC:N             │
│ RIV:VST|HY|+2.1|...                       │
├────────────────────────────────────────────┤
│ RAG top-5: ~100 tokens (opcional)         │
│ - V10: Safety Car desplegado              │
│ - V15: Boxes ALO duró 35s                │
├────────────────────────────────────────────┤
│ Trigger/pregunta: ~30 tokens              │
└────────────────────────────────────────────┘
Total: ~700-800 tokens
```

**Dependencias**: Fase 3 (RAG) primero, porque el ticker y el RAG se integran juntos en context_builder.py.

---

### Fase 5: Transporte Eficiente (MessagePack + Delta)
**Objetivo**: Reducir ancho de banda WebSocket para telemetría 20Hz.

#### ¿Por qué?
Telemetría completa como JSON a 20Hz: ~200 bytes × 20 = ~4 KB/s por cliente. Con MessagePack (~120 bytes) + delta encoding (~20-50 bytes delta): ~500 bytes/s promedio. Para 50 clientes simultáneos: ~25 KB/s vs 200 KB/s.

#### Tareas concretas

**T5.1: Instalar librerías**
```bash
pip install msgpack
npm install @msgpack/msgpack
```

**T5.2: Serialización MessagePack**
- Frontend: `encode(frame)` → Uint8Array → WebSocket binario
- Backend: `decode(data)` → dict → `latest_client_frame`

**T5.3: Delta encoding**
- Frontend: comparar frame actual con anterior, enviar solo campos que cambiaron
- Campo `_t`: timestamp del frame (para que backend sepa si perdió algún delta)
- Backend: aplicar delta sobre `latest_client_frame` existente

**T5.4: Snapshot completo cada 5s**
- Cada 100 frames (~5s), enviar frame completo (no delta)
- Backend: si detecta gap en `_t`, pedir resync (o esperar al próximo snapshot)

#### Flujo
```
Frontend                           Backend
   │                                  │
   ├── JSON "telemetry" (Fase 0) ───→ │ Fase inicial
   │   200 bytes a 20Hz = 4 KB/s     │
   │                                  │
   ├── MessagePack delta ──────────→ │ Fase 5
   │   ~30 bytes a 20Hz = 600 B/s   │
   │   + snapshot c/5s = ~120 B     │
   │   Total: ~650 B/s              │
   │                                  │
   └── Si gap detectado ────────────→ │
       (re-sync en próximo snapshot)  │
```

**Dependencias**: Fase 0 (telemetría básica funcionando primero).

---

### Fase 6: Correcciones Tests y Código
**Objetivo**: Tests pasando, código limpio, sin duplicaciones.

#### Tareas

**T6.1: Actualizar tests TTS al router real**
- **Archivo**: `backend/tests/test_tts.py`
- **Qué**: Tests actualizados para el router real (edge_tts_service, truncado 2000 chars)
- **Estado**: ✅ Plan ya escrito en `docs/plans/2026-05-23-correccion-flujo-ingeniero.md` (Task 3.1)

**T6.2: Migrar test_llm_async al nuevo VLLMClient**
- **Archivo**: `backend/tests/test_llm_async.py`
- **Qué**: Tests para el nuevo `VLLMClient` (OpenAI SDK, no el viejo Groq)
- **Estado**: ✅ Plan ya escrito (Task 3.3)

**T6.3: Limpiar TS6133 (unused vars)**
- **Archivos**: Varios TS
- **Qué**: Eliminar variables declaradas pero no usadas
- **Por qué**: `tsc --noEmit` da 12 errores, no bloquean pero son ruido

**T6.4: Unificar dos clientes LLM**
- **Archivos**: `backend/src/services/llm_service.py`, `backend/src/intelligence/llm_client.py`
- **Qué**: `llamar_copiloto_stream()` en `llm_service.py` debe usar `VLLMClient` internamente
- **Por qué**: Hay DOS implementaciones del cliente LLM (httpx directo + OpenAI SDK)
- **Estado**: ✅ Plan ya escrito en `docs/plans/2026-05-22-ingeniero-robustez.md` (Task 3.1)

**T6.5: TTS_BACKEND en .env**
- **Archivo**: `backend/.env`
- **Qué**: Cambiar `TTS_BACKEND=gemini` → `TTS_BACKEND=edge` (si sigue mal)
- **Estado**: ✅ Ya está en edge en el `.env` actual

**T6.6: edge-tts en pyproject.toml**
- **Archivo**: `backend/pyproject.toml`
- **Qué**: Añadir `"edge-tts>=7.0.0"` a dependencias
- **Por qué**: Está instalado pero no declarado (falla en fresh venv)

**T6.7: Eliminar GEMINI_API_KEY hardcodeada**
- **Archivo**: `backend/src/config.py`
- **Qué**: Cambiar default `GEMINI_API_KEY: str = ""` (no hardcodeada)
- **Por qué**: La clave está expuesta en el repositorio

**T6.8: Edge TTS timeout 30s**
- **Archivo**: `backend/src/services/edge_tts_service.py`
- **Qué**: Envolver `_stream()` con `asyncio.wait_for()`
- **Por qué**: Sin timeout, Azure puede colgar la request para siempre

**T6.9: Alinear truncamiento TTS 500→2000**
- **Archivo**: `frontend/src/hooks/useWebSocket.ts`
- **Qué**: Cambiar límite de truncamiento de 500 a 2000 chars
- **Por qué**: El backend acepta hasta 2000, el frontend corta en 500

**T6.10: Capability global-shortcut en Tauri**
- **Archivo**: `frontend/src-tauri/tauri.conf.json`
- **Qué**: Añadir permisos para `global-shortcut` plugin
- **Por qué**: Si falta, los atajos de teclado globales no funcionan

**T6.11: Cache TTL en lmu_api.py**
- **Archivo**: `backend/src/services/lmu_api.py`
- **Qué**: Añadir timestamps a caches para detectar datos obsoletos
- **Por qué**: Los caches crecen sin límite

---

### Fase 7: Soporte Windows Sidecar (Tauri)

**T7.1: Sidecar con PyInstaller**
- Empaquetar `sidecar/main.py` como `.exe` con PyInstaller
- Opciones: `--onefile --noconsole`
- Salida: `sidecar/dist/strategy_sidecar.exe`

**T7.2: Tauri sidecar integration**
- En `tauri.conf.json`: `"bundle": { "externalBin": ["../sidecar/dist/strategy_sidecar.exe"] }`
- En Rust/Tauri: `app.shell().sidecar("strategy_sidecar")` al arrancar
- Comunicación: WebSocket localhost (o stdin/stdout pipe)
- Matar sidecar al cerrar Tauri

**T7.3: Detección de caída del sidecar**
- Si el sidecar se cae, Tauri debe reiniciarlo automáticamente
- Health check cada 5s vía WebSocket
- Si no responde: matar proceso, reiniciar, loguear

---

### Fase 8: Optimizaciones y Mejoras

**T8.1: Audios pregrabados para alertas**
- Mapear `AlertMessage.alert_id` → archivo `.wav`
- Spotter no usa TTS (más rápido, menos recursos)
- Categorías: pits, safety car, gap, límite, combustible, neumáticos
- Prioridad: Media (ahorra ~500ms por alerta)

**T8.2: Protección time jump en triggers**
- **Archivo**: `backend/src/intelligence/triggers.py`
- **Qué**: Detectar saltos de `time.monotonic()` (hibernación/suspensión)
- **Por qué**: Si Windows hiberna, al reanudar todos los triggers expiran a la vez
- **Plan**: ✅ Ya en `docs/plans/2026-05-22-ingeniero-robustez.md` (Task 2.3)

**T8.3: Logging con advice_id**
- Añadir `advice_id` a todos los logs del flujo LLM
- Ayuda a trazar problemas: WebSocket → engine → LLM → respuesta
- Archivos: `engine.py`, `llm_client.py`, `websocket.py`

**T8.4: Silenciar error de desconexión WebSocket**
- **Archivo**: `backend/src/routers/websocket.py`
- **Qué**: Capturar `RuntimeError: Cannot call "receive" once a disconnect message has been received`
- **Por qué**: Es ruido inofensivo cada vez que un cliente se desconecta

**T8.5: WebSocket reconnect con state recovery (post-MVP)**
- Al reconectar, frontend solicita estado actual del engine
- Backend devuelve: modo radio, últimos mensajes, telemetría
- Evita que el frontend se quede sin estado tras reconexión

---

## Dependencias entre fases (orden de implementación)

```
Fase 0b (TypeScript fixes) ─→ Fase 0 (WS Telemetría)
                                    │
                                    ├→ Fase 1 (Correcciones robustez)
                                    │      │
                                    │      └→ Fase 2 (Sidecar Windows)
                                    │             │
                                    │             └→ Fase 3 (RAG)
                                    │                    │
                                    │                    └→ Fase 4 (Ticker)
                                    │
                                    └→ Fase 5 (Transporte) ─ (independiente)
                                              │
                                              └→ Fase 7 (Tauri sidecar)

Fase 6 (Tests/código) ─→ independiente, en paralelo con cualquier fase
Fase 8 (Optimizaciones) ─→ independiente, después de estabilidad
```

## Orden recomendado ahora

1. **🔴 Fase 0b**: Reparar `usePTT.ts` (3 errores de tipo) — el PTT no funciona
2. **🔴 Fase 0**: WebSocket Telemetría — datos reales para estrategia
3. **🟡 Fase 1**: Correcciones rápidas (timeouts, cola TTS, selectores)
4. **🟡 Fase 6.4**: Unificar dos clientes LLM
5. **🟢 Fase 6.6**: edge-tts en pyproject.toml
6. **🟢 Fase 6.7**: Eliminar GEMINI_API_KEY hardcodeada
