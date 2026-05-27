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
- **Ticker compacto (F4):** ✅ `generate_ticker()` reemplaza JSON verboso por texto ~400 tokens
- **Prompt Builder (F4):** ✅ `SYSTEM_PROMPT_TICKER` con tabla diccionario + contexto RAG embebido
- **LiveContext (F0/F4):** ✅ Snapshots con `speed`, `track_grip_level`, `update_realtime()`

### Backend tests: ✅ 285 tests pasando (cov 69%, +11.5pts vs 26-mayo)

### Estado del frontend (React/TypeScript/Tauri)
- ✅ 55 tests unitarios pasando (Vitest)
- ✅ 0 errores TypeScript (tsc --noEmit limpio)
- ✅ PTT funcional, tsc --noEmit limpio
- ✅ MessagePack binario + delta encoding implementado

---

## Lecciones Aprendidas — Infraestructura LLM

| Síntoma | Causa | Solución |
|---------|-------|----------|
| `"No connected db."` | 2 instancias LiteLLM peleando puerto 4000 | Matar todas, reiniciar con `--config` |
| `"LLM Provider NOT provided"` | Faltaba prefijo `openai/` en modelo | `model: openai/qwen3.5-4b.mq4` |
| `"Missing credentials"` | Provider openai requiere api_key | `api_key: REDACTED` en config |
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
      api_key: REDACTED
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
│  RAG (FASE 3): ChromaDB + multilingual-e5-large ✅           │ │
│    └→ Historial de eventos + snapshots por vuelta             │ │
│    └→ Top-5 eventos históricos en prompt                      │ │
│                                                              │ │
│  Ticker (FASE 4): formato compacto para prompts ✅            │ │
│    └→ DRV|TYR|BRK|GAP|SES|WTH|RIV en ~400 tokens             │ │
│    └→ generate_ticker() + SYSTEM_PROMPT_TICKER                │ │
│    └→ _build_ticker_data() normaliza 3 fuentes + REST API     │ │
│                                                              │ │
│  LiveContextManager (F0/F4): snapshots mejorados ✅           │ │
│    └→ speed, track_grip, cloud_coverage, raining              │ │
│    └→ update_realtime() entre vueltas                         │ │
│    └→ damage[aero] corregido (no brake_wear)                 │ │
│                                                              │ │
│  Transporte (FASE 5): MessagePack + Delta encoding            │ │
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

### Fase 0: WebSocket Telemetría (F0) — ✅ COMPLETADA
**Objetivo**: Que el frontend Windows envíe telemetría real al backend Linux para estrategias reales.

#### Tareas concretas

**T0.1: Handler `telemetry` en websocket.py** ✅
- El backend ya recibe WebSocket del frontend
- Falta un `if event == "telemetry": app_state.latest_client_frame = data`
- Ya está el health check que reporta `frontend_telemetry.received`
- Archivo: `backend/src/routers/websocket.py` (~línea 183)

**T0.2: Strategy loop use latest_client_frame** ✅
- `strategy_sender_loop` usa `reader.get_state()` (simulado)
- Cambiar a: intentar `latest_client_frame` primero, fallback a reader
- Archivo: `backend/src/routers/websocket.py` (~línea 105)

**T0.3: Inicializar latest_client_frame en main.py** ✅
- `app.state.latest_client_frame = None`
- Cambiar `TelemetryReader(offline=True)` explícitamente
- Archivo: `backend/src/main.py` (~línea 59)

**T0.4: Frontend enviar telemetría a 20Hz** ✅
- `useWebSocket.ts`: añadir `useEffect` con `setInterval(sendJson("telemetry", lastTelemetry), 50)`
- Archivo: `frontend/src/hooks/useWebSocket.ts`

**T0.5: Test de integración WebSocket** ✅
- Script Python que envía telemetría simulada y verifica `health`
- Verificar que `frontend_telemetry.received: true`

**Nota de implementación**: Implementada junto con Fase 5 como transporte MessagePack binario + delta

---

### Fase 0b: Reparar errores TypeScript del frontend — ✅ COMPLETADA
**Objetivo**: Que el frontend compile sin errores para poder desarrollar.

#### ¿Por qué?
Hay 3 errores reales en `usePTT.ts` que impiden el funcionamiento del PTT:
1. Línea 78: `await` fuera de función `async` — la llamada a `sendBinary` está mal ubicada
2. Línea 89: `Uint8Array` no es `ArrayBuffer|Blob` — error de tipo en `sendBinary()`
3. Línea 99: `Expected 0 arguments, got 1` — función llamada con argumento que no acepta

Además, 12 errores TS6133 (variables declaradas pero no usadas) que no rompen la compilación pero ensucian.

**Archivo**: `frontend/src/hooks/usePTT.ts`

**Dependencias**: ❌ Ninguna. Se puede hacer ahora mismo.

**Nota de implementación**: 3 errores TS6133 corregidos. `tsc --noEmit`: 0 errores.

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

#### Arquitectura del sidecar (revisada 26 mayo)
```
Windows:
  shared-telemetry (real, 20Hz)
    ├→ StrategyRunner._process_cycle() cada 2s
    │    └→ TelemetryFrame → compute_strategy() → StrategyAdvice
    │    └→ brake_wear = 0.0 (DEUDA TÉCNICA: LMU shared memory no expone brake wear;
    │         REST API poller en sidecar pendiente para Fase 3+)
    │
    └→ StateChangeDetector (20Hz interno)
         ├→ detecta: posición, pits, gap, SC, clima, vuelta completada
         └→ genera: eventos + snapshots por vuelta
    
    WebSocket cliente → ws://LINUX_IP:8008/ws/sidecar
      └→ envía cada 2s: {event: "strategy_frame", data: {advice, frame, events, snapshot}}
```

> **⚠️ DEUDA TÉCNICA — brake_wear**: La shared memory de LMU solo expone `mBrakeTemp` y `mBrakePressure`. El `BrakeData.wear_thickness` del reader es siempre `[0,0,0,0]`. El backend obtiene brake wear vía REST API (`/rest/garage/UIScreen/RepairAndRefuel`). En Fase 2, el sidecar envía `brake_wear=0` y el subcomponente de frenos del `StrategyAdvice` siempre reporta "frenos OK". Esto afecta principalmente carreras endurance. Solución planificada: mini REST poller en sidecar (`http://localhost:6397`) en Fase 3 o cuando se requiera. Ver `findings.md` en `.planning/2026-05-26-fase-2-sidecar/`.

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

**T2.4: Endpoint `/ws/sidecar` + handler `strategy_frame`**
- Nuevo endpoint `/ws/sidecar` sin `telemetry_sender_loop` ni `strategy_sender_loop` fantasma
- Almacena `strategy_frame` en `app.state.latest_strategy_frame`
- `strategy_sender_loop` usa `latest_strategy_frame` primero, fallback a `strategy_service`
- Mantener `StrategyService(reader)` en Linux como fallback offline (no eliminar)

**T2.5: Tauri sidecar (futuro, Fase 5)**
- Empaquetar sidecar Python como binario (PyInstaller)
- Tauri lo gestiona: arrancar/parar junto con la app
- Comunicación: WebSocket localhost

**Dependencias**: Fase 0 (telemetría WebSocket) debe estar estable primero.

---

### Fase 3: RAG — Historial de Carrera ✅ COMPLETADA
**Objetivo**: Dar al LLM contexto histórico de la carrera (eventos pasados, ritmo rivales, degradación).

#### ¿Por qué?
El LLM actual solo ve el frame actual de telemetría. No sabe lo que pasó hace 10 vueltas, si un rival está en estrategia diferente, o cómo evoluciona la degradación. Con RAG, el prompt incluye los eventos relevantes más cercanos semánticamente a la pregunta/trigger actual.

#### Stack
- **Vector DB**: ChromaDB (simple, sin servidor, persistencia en disco, se borra al cerrar sesión)
- **Embedding model**: `multilingual-e5-large` (CPU, ~40ms por embedding, cola asíncrona)
- **Idioma**: español + inglés (modelo multilingüe)
- **Indexación**: Por evento detectado (NO cada 2s ni cada frame de telemetría)
- **Regla especial**: Vueltas 1-3 NO incluyen neumáticos en el embedding (desgaste no representativo)

#### Formato del embedding (texto plano para ChromaDB)

El embedding se genera sobre un texto compacto de la telemetría del MOMENTO del evento. Dos eventos con telemetría similar tendrán vectores cercanos en ChromaDB, independientemente del tipo de evento.

Formato por prefijos fijos (ver sección [Mapa completo de telemetría LMU](#mapa-completo-de-telemetría-lmu)):

```
L{vuelta}|P{posición}|F{combustibleL}|T{FL/Fr/RL/RR}|SC{S/N}|YF{S/N}|G{+ahead/-behind}|S{velocidad}|CLD{0-10}|RAIN{0.0-1.0}|WET{0.0-1.0}|A{tempC}|TEMP{tempC}|DRS{S/N}|PIT{0-4}|BAT{%}|D{aero_%}|E{tipo_evento}
```

Ejemplo real (Safety Car, V26, P3, lluvia ligera, neumáticos válidos):
```
L26|P3|F42.3|T72/68/65/63|SCS|YFS|G+2.1|S180|CLD6|RAIN0.3|WET0.4|A22|TEMP30|DRSN|PIT0|BAT85|D12|Esafety_car
```

Ejemplo V3 (sin neumáticos, regla especial):
```
L3|P5|F91.2|SCN|YFN|G-1.2|S175|CLD2|RAIN0.0|WET0.0|A20|TEMP32|DRSS|PIT0|BAT90|D2|Egap_change
```

**Cada evento en ChromaDB** (~4.9 KB c/u):
- Vector embedding (1024 floats × 4 bytes = 4,096 bytes)
- Texto embedido (~120 chars = ~120 bytes)
- Metadata: {type, lap, timestamp, session_type, race_id} (~100 bytes)
- Overhead ChromaDB (~600 bytes)

**Estimación por carrera (~35 vueltas, 92 eventos):** ~450 KB.**
**Estimación anual (~52 carreras semanales):** ~23 MB.

#### Flujo de indexación (diagrama)
```
Sidecar (Windows):
  StrategyRunner.process_cycle() cada 2s
    └→ StateChangeDetector.detect(frame)
         └→ TIERRA: nuevo = comparar con frame anterior
              └→ Si hay cambios → evento(s) detectado(s)
                   
Backend (Linux):  
  /ws/sidecar recibe strategy_frame (cada 2s)
    └→ Por cada evento en el batch:
         1. Tomar TelemetryFrame de ESE momento
         2. Convertir a texto plano (formato prefijos fijo)
         3. Si lap ≤ 3: omitir campo T (neumáticos)
         4. Embedding → ChromaDB store
         5. Metadata: {type, lap, timestamp, race_id, session_type}

Trigger automático (fuel_critical, pit_window, etc.) o pregunta piloto:
  Frame actual → mismo formato texto → embedding
    └→ ChromaDB query top-5 (filtro lap > 3 para neumáticos)
         └→ 5 eventos históricos con telemetría más similar
              └→ Se inyectan en el prompt del LLM (~100 tokens)

#### Tareas concretas ✅

**T3.1: Instalar ChromaDB + sentence-transformers** ✅ Instalado y verificado
```bash
pip install chromadb sentence-transformers
```
Descargar `multilingual-e5-large` (2.2 GB, cacheado en HF)

**T3.2: EventStore (`backend/src/persistence/event_store.py`)** ✅ Creado
- Clase que gestiona ChromaDB
- `store_event(event_type, data, metadata)` → inserta en colección
- `query(query_text, top_k=5)` → búsqueda semántica
- `store_snapshot(lap, driver, snapshot_data)` → por vuelta
- `get_snapshots(driver=None, lap_range=None)` → recuperar históricos

**T3.3: LiveContextManager — extensiones** ✅ Implementado (snapshots históricos + buffers)
- Guardar snapshots históricos por vuelta por driver
- Timeline de eventos para el prompt
- Buffers de ritmo: últimas 5 vueltas, top-10 rivales
- Buffers de desgaste: últimas 5 vueltas propias
- Exponer método `get_context_for_prompt(query, current_frame)` → RAG top-5 + buffers

**T3.4: Integrar RAG en context_builder.py** ✅ Integrado via `_build_rag_context()` en `context_builder.py`
- Al construir prompt para LLM, añadir top-5 eventos históricos
- Formato: `## RECORDATORIO HISTÓRICO\n- V10: Safety Car desplegado\n- V15: Boxes ALO\nduró 35s\n...`
- Límite: ~100 tokens de RAG por prompt

**Dependencias**: Sidecar (Fase 2) debe estar generando eventos/snapshots para que RAG tenga datos.

---

### Fase 4: Ticker Compacto + Prompt Builder ✅ COMPLETADA
**Objetivo**: Reducir el tamaño del prompt del LLM (~700-800 tokens total) para velocidad y economía.
**Implementación**: 26-mayo-2026, 204 tests backend, flujo completo verificado.

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

#### Tareas concretas ✅

**T4.1: `backend/src/intelligence/ticker.py`** ✅ Creado y testeado (30 tests)
- `generate_ticker(data: dict) -> str` que produce ticker compacto
- 6 líneas: DRV, BRK, GAP, SES, WTH, RIV (anillos de proximidad CLS1/CLS2/FAR/LAP)
- `abbreviate_name(name) -> str` para abreviar nombres a 3 chars
- Formato completo documentado en `LMU/rag-dictionary.md`

**T4.2: Detector de tokens** ✅ (seguridad, threshold ~3000 tokens con degradación de tier)
- degradación: RAG → RIV FAR → DRV básico
- No bloquea funcionalmente

**T4.3: Refactorizar context_builder.py** ✅
- `_build_ticker_data()` normaliza snapshot + telemetry + strategy + lmu_api en dict canónico
- `build_prompt()` acepta `telemetry_frame`, `strategy_advice`, `lmu_api` como kwargs
- Usa `generate_ticker()` en vez de JSON crudo
- Cobertura: modo ticker + modo legacy (backward compatible)

**T4.4: Actualizar prompt_templates.py** ✅
- `SYSTEM_PROMPT_TICKER` con tabla diccionario completa (~200 tokens)
- `render()` detecta modo ticker vs legacy automáticamente
- Prompt final: system + ticker + RAG + trigger ≈ ~730 tokens

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

### Fase 5: Transporte Eficiente (MessagePack + Delta) — ✅ COMPLETADA
**Objetivo**: Reducir ancho de banda WebSocket para telemetría 20Hz.

#### ¿Por qué?
Telemetría completa como JSON a 20Hz: ~200 bytes × 20 = ~4 KB/s por cliente. Con MessagePack (~120 bytes) + delta encoding (~20-50 bytes delta): ~500 bytes/s promedio. Para 50 clientes simultáneos: ~25 KB/s vs 200 KB/s.

#### Tareas concretas

**T5.1: Instalar librerías** ✅
```bash
pip install msgpack
npm install @msgpack/msgpack
```

**T5.2: Serialización MessagePack** ✅
- Frontend: `encode(frame)` → Uint8Array → WebSocket binario
- Backend: `decode(data)` → dict → `latest_client_frame`

**T5.3: Delta encoding** ✅
- Frontend: comparar frame actual con anterior, enviar solo campos que cambiaron
- Campo `_t`: timestamp del frame (para que backend sepa si perdió algún delta)
- Backend: aplicar delta sobre `latest_client_frame` existente

**T5.4: Snapshot completo cada 5s** ✅
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

#### Detalle técnico (implementación final)
- **20-50 bytes/frame delta**, snapshot 120 bytes cada 100 frames (5s a 20Hz)
- **Total ~650 B/s vs ~4 KB/s anteriores (~6× reducción)**
- Soporte sidecar priority en el flujo binario
- Delta tracking con sequence numbers para detección de gaps

#### Archivos creados
- `backend/src/services/msgpack_codec.py` (62 líneas, mypy strict)
- `frontend/src/services/msgpack.ts` (64 líneas)
- `backend/tests/test_msgpack_codec.py` (21 tests)
- `frontend/src/__tests__/msgpack.test.ts` (13 tests)
- `backend/tests/test_ws_integration.py` (11 tests)

#### Archivos modificados
- `backend/src/routers/websocket.py` (binario, delta, sidecar priority)
- `frontend/src/hooks/useWebSocket.ts` (binario, delta, tracking)

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

## Arquitectura de Voz — 3 Niveles (27 mayo 2026)

```
Telemetry 20Hz
  │
  ├→ Nivel 1: Reglas duras → TTS DIRECTO (20Hz, <50ms)
  │    ├── fuel < 3 vueltas → "Combustible crítico" 🗣️
  │    ├── SC activo → "Safety Car desplegado" 🗣️
  │    ├── gap < 0.5s → "Coche pegado" 🗣️
  │    ├── pit limiter → "Pit limiter no activado" 🗣️
  │    ├── daños → "Daños detectados" 🗣️
  │    ├── última vuelta → "Última vuelta" 🗣️
  │    └── entrada/salida pits → "Entrando en boxes" 🗣️
  │
  └→ Nivel 3: LLM + TTS (0.5Hz, ~1-3s)
       ├── Preguntas del piloto (PTT)
       └── Análisis estratégico complejo
```

**Flujo:** SpotterService/triggers `ALERT_ONLY` → AlertMessage → WebSocket → frontend → TTS queue → Edge TTS → 🗣️

### Deuda Técnica — Nivel 2 (Heurísticas programadas, p/mvp)

| Caso | Descripción | Por qué es deuda |
|------|-------------|:----------------:|
| Fuel + ventana pits | "Ventana de pits con combustible justo" | Combina 2 variables |
| Degradación acelerada | "Neumáticos cayendo rápido" | Requiere media móvil por vuelta |
| Rival en boxes | "Rival directo paró — undercut posible" | Requiere tracking de oponentes |
| Temperatura excesiva | "Neumáticos sobrecalentados" | Requiere umbral dinámico |
| Batería + tendencia | "Batería baja y descargando" | Requiere tendencia en ventana |

**Criterio de activación:** Si la condición necesita >1 fuente de datos o cálculo en ventana de N vueltas, es Nivel 2 → post-MVP.

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
Fase 0b (TypeScript fixes) ✅ ─→ Fase 0 (WS Telemetría) ✅
                                      │
                                      ├→ Fase 1 (Correcciones robustez) ✅
                                      │      │
                                      │      └→ Fase 2 (Sidecar Windows)
                                      │             │
                                      │             ├→ Fase 3 (RAG) ✅
                                      │             │      │
                                      │             │      └→ Fase 4 (Ticker) ✅
                                      │             │
                                      │             └─── Fase 5 (Transporte) ✅

Fase 6 (Tests/código) ─→ ✅ (236 tests backend pasando)
Fase 8 (Optimizaciones) ─→ pendiente, post-MVP
```

---

## Mapa completo de telemetría LMU (shared memory)

> Fuente: `shared-telemetry/shared_telemetry/pyLMUSharedMemory/lmu_data.py` (mapping oficial de la estructura C de LMU)

### Bloque 1: Contexto de sesión — `data.scoring.scoringInfo`

| Campo LMU | Tipo | Rango | Descripción |
|-----------|------|-------|-------------|
| `mTrackName` | str[64] | — | Nombre del circuito |
| `mSession` | int | 0-13 | 0=TestDay, 1-4=Practice, 5-8=Qual, 9=Warmup, 10-13=Race |
| `mCurrentET` | double | — | Tiempo actual de sesión (segundos) |
| `mEndET` | double | — | Tiempo final de sesión |
| `mMaxLaps` | int | — | Vueltas máximas (0 si es por tiempo) |
| `mLapDist` | double | — | Longitud del circuito (metros) |
| `mNumVehicles` | int | 0-104 | Número actual de vehículos |
| `mGamePhase` | ubyte | 0-9 | 5=Green, 6=SC/FCY, 8=SessionOver |
| `mYellowFlagState` | char | -1-7 | Estado FCY: 0=None, 1=Pending, 4=PitsOpen |
| `mSectorFlag` | ubyte[3] | — | Bandera amarilla por sector |
| `mDarkCloud` | double | 0.0-1.0 | Nubosidad |
| `mRaining` | double | 0.0-1.0 | Intensidad de lluvia |
| `mAmbientTemp` | double | °C | Temperatura ambiente |
| `mTrackTemp` | double | °C | Temperatura pista |
| `mWind` | LMUVect3 | — | Velocidad del viento (x,y,z) |
| `mMinPathWetness` | double | 0.0-1.0 | Mojado mínimo de la trazada |
| `mMaxPathWetness` | double | 0.0-1.0 | Mojado máximo de la trazada |
| `mAvgPathWetness` | double | 0.0-1.0 | Mojado promedio de la trazada |
| `mSessionTimeRemaining` | float | segundos | Tiempo restante de sesión |
| `mTimeOfDay` | float | horas | Hora del día en la simulación |
| `mTrackGripLevel` | uint8 | 0-4 | 0=Green, 1=Low, 2=Medium, 3=High, 4=Saturated |
| `mCloudCoverage` | uint8 | 0-10 | 0=Clear → 10=Overcast&Storm |
| `mGameMode` | ubyte | 1-3 | 1=Server, 2=Client, 3=ServerAndClient |

### Bloque 2: Vehicle scoring (hasta 104 vehículos) — `data.scoring.vehScoringInfo[i]`

| Campo LMU | Tipo | Descripción |
|-----------|------|-------------|
| `mID` | int | Slot ID del vehículo |
| `mDriverName` | char[32] | Nombre del piloto |
| `mVehicleName` | char[64] | Nombre del coche |
| `mTotalLaps` | short | Vueltas completadas |
| `mSector` | byte | 0=sector3, 1=sector1, 2=sector2 |
| `mLapDist` | double | Distancia en vuelta actual (metros) |
| `mBestLapTime` | double | Mejor tiempo de vuelta (segundos) |
| `mLastLapTime` | double | Último tiempo de vuelta |
| `mBestSector1` / `mBestSector2` | double | Mejores sectores |
| `mLastSector1` / `mLastSector2` | double | Últimos sectores |
| `mCurSector1` / `mCurSector2` | double | Sectores actuales |
| `mNumPitstops` | short | Paradas en boxes realizadas |
| `mNumPenalties` | short | Penalizaciones pendientes |
| `mIsPlayer` | bool | ¿Es el jugador local? |
| `mPlace` | ubyte | Posición (1-based) |
| `mVehicleClass` | char[32] | Clase del vehículo (Hypercar, GT3, etc.) |
| `mInPits` | bool | ¿Está en pits? |
| `mPitState` | ubyte | 0=none, 1=request, 2=entering, 3=stopped, 4=exiting |
| `mTimeBehindNext` | double | Gap con el siguiente (segundos) |
| `mTimeBehindLeader` | double | Gap con el líder |
| `mLapsBehindNext` / `mLapsBehindLeader` | int | Vueltas perdidas |
| `mTimeIntoLap` | double | Tiempo estimado en vuelta actual |
| `mEstimatedLapTime` | double | Tiempo estimado de vuelta |
| `mFuelFraction` | ubyte | Combustible restante (0x00=0%, 0xFF=100%) |
| `mFlag` | ubyte | Bandea primary (0=Green, 6=Blue) |
| `mUnderYellow` | bool | ¿Ha pasado bajo bandera amarilla? |
| `mDRSState` | bool | ¿DRS activo? |
| `mInGarageStall` | bool | ¿En plaza de garaje? |
| `mFinishStatus` | byte | 0=none, 1=finished, 2=dnf, 3=dq |

### Bloque 3: Vehicle telemetry (hasta 104 vehículos) — `data.telemetry.telemInfo[i]`

| Grupo | Campos | Key para embedding |
|-------|--------|-------------------|
| **Posición** | `mPos` xyz, `mLocalVel` xyz, `mLocalAccel` xyz | Velocidad (`S`) |
| **Motor** | `mGear` (-1=R,0=N,1+), `mEngineRPM`, `mEngineMaxRPM`, `mEngineWaterTemp`, `mEngineOilTemp`, `mEngineTorque`, `mTurboBoostPressure` | — (no embed, útil para contexto) |
| **Inputs** | `mFilteredThrottle`, `mFilteredBrake`, `mFilteredSteering`, `mFilteredClutch` (0.0-1.0) | — |
| **Combustible** | `mFuel`, `mFuelCapacity` | `F` (litros) |
| **Híbrido** | `mStateOfCharge` (%), `mBatteryChargeFraction`, `mElectricBoostMotorState` (0-3), `mRegen` (kW), `mVirtualEnergy` | `BAT` (%) |
| **Ruedas (4×)** | `mBrakeTemp`, `mBrakePressure`, `mWear`, `mPressure`, `mTemperature[3]`, `mTireCarcassTemperature`, `mOptimalTemp`, `mCompoundIndex`, `mCompoundType` (0=Soft,1=Medium,2=Hard,3=Wet), `mSurfaceType`, `mFlat`, `mCamber`, `mToe`, `mGripFract` | `T` (wear FL/FR/RL/RR) |
| **Aero** | `mDrag`, `mFrontDownforce`, `mRearDownforce`, `mFrontWingHeight`, `mFrontRideHeight`, `mRearRideHeight` | — |
| **Daños** | `mDentSeverity[8]`, `mDetached`, `mLastImpactMagnitude` (N), `mLastImpactPos` | `D` (daño aero %) |
| **Electrónica** | `mABSActive`, `mTCActive`, `mABS` (0-Max), `mTC`, `mTCSlip`, `mMotorMap`, `mRearFlapActivated`, `mWiperState`, `mHeadlights`, `mIgnitionStarter` | `DRS` (rear flap) |
| **Gaps** | `mTimeGapCarAhead`, `mTimeGapCarBehind`, `mTimeGapPlaceAhead`, `mTimeGapPlaceBehind`, `mDeltaBest` | `G` (gap adelante/atrás) |
| **Penalizaciones** | `mLapInvalidated`, `mTrackLimitsSteps`, `mSpeedLimiterActive`, `mOverheating` | — |
| **Vuelta** | `mLapNumber`, `mCurrentSector`, `mDeltaTime`, `mElapsedTime`, `mScheduledStops` | `L` (vuelta) |

### Prefijos del formato de embedding

| Prefijo | Campo LMU | Ejemplo | Notas |
|---------|-----------|---------|-------|
| `L` | `mLapNumber` | `L26` | Vuelta actual |
| `P` | `mPlace` | `P3` | Posición |
| `F` | `mFuel` | `F42.3` | Combustible en litros (1 decimal) |
| `T` | `mWheels[i].mWear` | `T72/68/65/63` | Desgaste neumáticos FL/FR/RL/RR (%). Omitir si lap ≤ 3 |
| `SC` | `mGamePhase == 6` | `SCS` o `SCN` | Safety Car activo |
| `YF` | `mSectorFlag` + `mYellowFlagState` | `YFS` o `YFN` | Bandera amarilla activa |
| `G` | `mTimeGapPlaceAhead`/`Behind` | `G+2.1` o `G-1.2` | Gap con siguiente/anterior. Signo + = por delante |
| `S` | `mLocalVel` (magnitud) | `S180` | Velocidad en m/s (entero) |
| `CLD` | `mCloudCoverage` | `CLD4` | Cobertura nubes 0-10 |
| `RAIN` | `mRaining` | `RAIN0.3` | Lluvia 0.0-1.0 |
| `WET` | `mAvgPathWetness` | `WET0.4` | Mojado pista 0.0-1.0 |
| `A` | `mAmbientTemp` | `A22` | Temperatura ambiente °C |
| `TEMP` | `mTrackTemp` | `TEMP30` | Temperatura pista °C |
| `DRS` | `mDRSState` / `mRearFlapActivated` | `DRSS` o `DRSN` | DRS activo |
| `PIT` | `mPitState` | `PIT0` | 0=none, 1=request, 2=entering, 3=stopped, 4=exiting |
| `BAT` | `mStateOfCharge` | `BAT85` | Batería híbrido % |
| `D` | `mDentSeverity` (promedio) | `D12` | Daños acumulados % (proxy) |
| `E` | Tipo de evento StateChangeDetector | `Elap_completed` | Tipo de evento que disparó este embedding |

---

## v1.1 — Recopilación centralizada de datos de carrera (post-MVP)

### Visión general
Acumular embeddings + eventos de carreras de TODOS los clientes para construir un dataset creciente que mejore la calidad del RAG con el tiempo. En Le Mans Ultimate hay carreras semanales que la gente corre regularmente. Almacenar estos datos permite que el LLM encuentre patrones estadísticos ("¿cuándo fue la última vez que pasó X en condiciones similares?") a través de cientos de carreras.

### Estado actual (MVP)
- ChromaDB se crea por sesión y **se elimina al cerrar la aplicación**
- No hay recopilación externa de datos
- El RAG solo funciona intra-carrera (una sola sesión)

### Objetivo v1.1
1. Al final de cada carrera, exportar la colección ChromaDB a JSON
2. Enviar al servidor central vía HTTP POST
3. El servidor central acumula en una ChromaDB maestra
4. Los clients pueden consultar la DB maestra para búsqueda cross-carrera

### Arquitectura

```
Cliente (Windows):
  ChromaDB local (se borra al cerrar)
    └→ Detectar fin de carrera (mGamePhase == 8)
         └→ Exportar race_id, track, eventos + embeddings
              └→ POST /api/v1/collect → Servidor central

Servidor central:
  POST /api/v1/collect
    └→ Verificar API key
    └→ Almacenar en ChromaDB maestra
         └→ Metadata adicional: client_id, game_version, date
```

### Formato del payload de exportación

```json
{
  "race_id": "uuid-v4",
  "client_id": "anon-client-hash",
  "track": "spa",
  "date": "2026-06-01T20:00:00Z",
  "session_type": "race",
  "total_events": 92,
  "game_version": "1.5.2",
  "events": [
    {
      "text": "L26|P3|F42.3|T72/68/65/63|SCS|YFS|G+2.1|S180|...|Egap_change",
      "embedding": [0.123, -0.456, ...],
      "metadata": {
        "type": "gap_change",
        "lap": 26,
        "timestamp": 1234.5
      }
    }
  ]
}
```

**Tamaño típico por carrera**: ~92 eventos × 4.9 KB = **~450 KB**.
**Tamaño anual (52 carreras)**: ~23 MB.

### Endpoint del servidor central

```python
@router.post("/api/v1/collect")
async def collect_race(data: dict, api_key: str = Header(...)):
    """Recibe datos de carrera de un cliente para la ChromaDB maestra."""
    verify_api_key(api_key)
    
    # Enriquecer metadata con info del cliente
    enriched_metadatas = []
    for e in data["events"]:
        enriched_metadatas.append({
            **e["metadata"],
            "race_id": data["race_id"],
            "track": data["track"],
            "date": data["date"],
            "client_id": data["client_id"],
            "session_type": data["session_type"],
        })
    
    master_collection.add(
        documents=[e["text"] for e in data["events"]],
        embeddings=[e["embedding"] for e in data["events"]],
        metadatas=enriched_metadatas,
    )
    return {"stored": len(data["events"]), "total_in_db": master_collection.count()}
```

### Detección de fin de carrera en el sidecar

```python
def check_race_end(frame: TelemetryFrame, scoring_info) -> Optional[str]:
    """Detecta si la carrera terminó. Devuelve race_id o None."""
    # Opción 1: Game phase cambió a 8 (SessionOver)
    if scoring_info.mGamePhase == 8:
        return str(uuid.uuid4())
    # Opción 2: El piloto cruzó la línea después de mMaxLaps
    if frame.lap_number > scoring_info.mMaxLaps and scoring_info.mMaxLaps > 0:
        return str(uuid.uuid4())
    return None
```

### Tareas concretas (cuando se implemente)

| Tarea | Archivo | Tiempo |
|-------|---------|--------|
| T1.1: Método `export_race()` en EventStore | `event_store.py` | 30 min |
| T1.2: Detectar fin de carrera en sidecar | `strategy_runner.py` | 30 min |
| T1.3: Endpoint `POST /api/v1/collect` | `collect_router.py` | 30 min |
| T1.4: Subida asíncrona al finalizar carrera | `event_store.py` | 30 min |
| T1.5: Autenticación API key simple | `collect_router.py` | 15 min |
| **Total** | | **~2 horas** |

### Consideraciones futuras
- **Privacidad**: `client_id` debe ser anónimo (hash de hardware, no Steam ID)
- **Versiones**: Embeddings de distintas versiones del modelo no son compatibles. Al actualizar el modelo, re-indexar
- **Consentimiento**: Opción en configuración para desactivar la recopilación
- **Frecuencia**: Una subida por carrera al finalizar (no tiempo real)
- **Servidor**: Podría ser un simple VPS con ChromaDB + FastAPI. Coste mínimo (~5€/mes)
- **Recompensa**: A futuro, el dataset permite fine-tuning de un modelo pequeño para predicción de estrategia

