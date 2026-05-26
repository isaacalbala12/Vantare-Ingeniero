# 🏎️ Vantare Ingeniero IA — Orquestador de Proyecto

## ¿Qué es?
Ingeniero de carreras con IA para Le Mans Ultimate. Escucha voz, analiza telemetría en tiempo real, responde con voz sintetizada y calcula estrategia. Distribuido en dos PCs (Windows con LMU + frontend Tauri; Linux con LLM local, LiteLLM y backend FastAPI).

Inspirado en CrewChief V4 para el motor determinista, pero extendido con LLM para razonamiento táctico.

## Estado actual (26 mayo 2026)
- Telemetría LMU: ✅ 20 Hz vía shared memory (Windows).
- Motor determinista: ✅ shared-strategy funcional (combustible, neumáticos, pits).
- LLM local: ✅ Qwen 3.5 4B MQ4 en Hipfire (Vulkan), streaming SSE.
- LiteLLM: ✅ proxy en :4000, OpenAI-compatible, expuesto por Cloudflare Tunnel.
- TTS: ✅ Edge TTS (es-ES-AlvaroNeural), ~500ms.
- Flujo HTTP texto→voz: ✅ completo.
- WebSocket telemetría en vivo: ⚠️ pendiente de reparar (backend no recibe telemetría del frontend).
- SpotterService: ✅ funcional (20Hz, 8 alertas deterministas, bypass LLM).

## Decisiones técnicas clave
- Python 3.12+, FastAPI + WebSocket.
- Hipfire + LiteLLM para inferencia local con API OpenAI.
- Edge TTS gratuito, sin consumo de VRAM.
- Cloudflare Tunnel para exponer LLM sin abrir puertos.
- React + Zustand, Tauri (no Electron) para frontend ligero.
- Qwen 3.5 4B base (no QwOPUS — tool calling descartado por latencia y calidad español).
- **3 capas de contexto para LLM**: Transporte (MessagePack+Delta), Snapshot (Ticker compacto), Historial (RAG con multilingual-e5-large).
- **2 flujos separados**: Spotter 20Hz sin LLM / Inteligencia on-demand con LLM.
- **Windows sidecar**: StrategyService + StateChangeDetector como proceso Python → Tauri sidecar en beta.
- **Arquitectura de contexto documentada en**: `docs/superpowers/specs/2026-05-26-arquitectura-contexto-llm-design.md`

---

## Roadmap completo (orden sugerido)

### Fase 0: Reparar WebSocket (CRÍTICO — permite desarrollo)
1. **websocket.py** → handler para recibir evento `"telemetry"` del frontend + guardar en `latest_client_frame`
2. **strategy_sender_loop** → usar `latest_client_frame` en vez de `reader.get_state()` (fallback a reader)
3. **useWebSocket.ts** → loop que envía `sendJson("telemetry", frame)` cada 50ms desde frontend
4. **main.py** → `TelemetryReader(offline=True)` para Linux (sin shared memory)

### Fase 1: Sidecar StrategyService en Windows
1. **Crear `sidecar/`** → proceso Python independiente con shared-telemetry + shared-strategy
2. **StateChangeDetector** → `shared-telemetry/shared_telemetry/event_detector.py` (nuevo)
   - Detectar cambios de posición, pits, gaps, safety car, clima, degradación
   - Generar eventos + snapshots por vuelta por driver
3. **WebSocket cliente** → sidecar envía eventos + ticker al backend Linux
4. **main.py** → eliminar `StrategyService(reader)` del backend Linux (pasa al sidecar)
5. **websocket.py** → handler `"strategy_frame"` para recibir resultados del sidecar

### Fase 2: RAG — Historial de carrera
1. **ChromaDB/LanceDB** → instalación y configuración en backend Linux
2. **multilingual-e5-large** → integración para embeddings en CPU
3. **EventStore** → `backend/src/persistence/event_store.py` (nuevo)
   - Almacenar eventos + snapshots en ChromaDB
   - Recuperar top-5 eventos por query semántica
4. **LiveContextManager** → extender con snapshots históricos por vuelta
   - Buffers de ritmo (últimas 5 vueltas, top-10 rivales)
   - Buffers de desgaste (últimas 5 vueltas propias)
   - Timeline de eventos para el prompt

### Fase 3: Ticker compacto + Prompt Builder
1. **`backend/src/intelligence/ticker.py`** (nuevo)
   - Generar formato ticker desde TelemetryFrame
   - Incluir: DRV, GAP, TYR, BRK, SES, WTH, RIV (40 rivales en tabla compacta)
2. **`context_builder.py`** → refactorizar para usar ticker + RAG + system prompt
   - Prompt de 700-800 tokens (system + ticker + RAG top-5 + trigger/pregunta)
3. **`prompt_templates.py`** → actualizar SYSTEM_PROMPT con instrucciones de parseo del ticker
4. **Detector de tokens** → `tiktoken` para calcular tokens antes de enviar al LLM
   - Si >500 tokens → reproducir radio pregrabada "Un momento, déjame consultarlo..."
5. **Pipeline de pregunta del piloto** → ticker completo + timeline completo + pregunta

### Fase 4: Transporte eficiente
1. **MessagePack** → `pip install msgpack` + `npm install @msgpack/msgpack`
2. **Delta encoding** → diff entre frames consecutivos (solo campos cambiados)
3. **Snapshot completo cada 5s** → para drift protection
4. **useWebSocket.ts** → enviar deltas en vez de telemetría completa

### Fase 5: Optimizaciones y Beta
1. **Audios pregrabados** → mapear `AlertMessage.alert_id` → archivo `.wav` local
2. **Tauri sidecar** → empaquetar sidecar Python dentro de Tauri (C2)
3. **Soft Prompting** → investigación: entrenar encoder de telemetría (investigación)
4. **Multi-cliente** → auth + rate limiting si aplica
5. **Código limpio** → eliminar legacy CrofAI, imports no usados

---

## Tareas inmediatas (orden sugerido)

### Bloque A: WebSocket (Fase 0)
1. ✅ SYSTEM_PROMPT_BASIC: respuestas naturales, abiertas, sin arrogancia.
2. 🔧 **websocket.py** → handler `"telemetry"` para recibir telemetría del frontend
3. 🔧 **useWebSocket.ts** → `sendJson("telemetry", frame)` cada 50ms
4. 🔧 **main.py** → `TelemetryReader(offline=True)` para Linux

### Bloque B: Sidecar + StateChangeDetector (Fase 1)
5. 🔧 **sidecar/** → proceso Python con shared-telemetry + shared-strategy
6. 🔧 **event_detector.py** → StateChangeDetector (detección de eventos + snapshots)
7. 🔧 **main.py** → eliminar StrategyService del backend, recibir del sidecar
8. 🔧 **websocket.py** → handler `"strategy_frame"` para recibir del sidecar

### Bloque C: RAG (Fase 2)
9. 🔧 **ChromaDB** → instalación y event_store.py
10. 🔧 **multilingual-e5-large** → integración embeddings en CPU
11. 🔧 **LiveContextManager** → extender con snapshots históricos

### Bloque D: Ticker + Prompt (Fase 3)
12. 🔧 **ticker.py** → generador de formato compacto
13. 🔧 **context_builder.py** → refactorizar con ticker + RAG + system prompt
14. 🔧 **prompt_templates.py** → SYSTEM_PROMPT con parseo de ticker
15. 🔧 **tiktoken** → detector de tokens para radio de espera

### Bloque E: Transporte (Fase 4)
16. 🔧 **MessagePack** → instalación y serialización
17. 🔧 **Delta encoding** → diff en frontend + reconstrucción en backend

---

## Comandos de prueba
```bash
# Probar SYSTEM_PROMPT_BASIC (sin telemetría)
curl -X POST http://localhost:8008/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Cuánto es 2+2?"}'

# Probar WebSocket (después de reparación)
# Frontend debe enviar: sendJson("telemetry", frame)
# Backend debe recibir y procesar en strategy_sender_loop

# Probar sidecar (Fase 1)
cd sidecar && python main.py

# Probar RAG (Fase 2)
python -c "from src.persistence.event_store import EventStore; es = EventStore(); es.query('fuel critical')"

# Probar ticker (Fase 3)
python -c "from src.intelligence.ticker import generate_ticker; print(generate_ticker(frame))"

# Probar token count (Fase 3)
python -c "import tiktoken; enc = tiktoken.get_encoding('cl100k_base'); print(len(enc.encode(prompt)))"
```

## Historial de decisiones
2026-05-26: Arquitectura de contexto validada → 3 capas (Transporte, Ticker, RAG) + 2 flujos (Spotter/Inteligencia).
2026-05-26: Tool Calling con QwOPUS descartado → Progressive Disclosure + RAG más eficiente y fiable.
2026-05-26: Windows sidecar (B→C2) para StrategyService → shared memory real, sin simulación.
2026-05-26: multilingual-e5-large en CPU para embeddings (2.2 GB RAM, ~40ms, español).
2026-05-26: SYSTEM_PROMPT_BASIC corregido - respuesta natural y abierta, sin arrogancia.
2026-05-26: Roadmap completo definido en 6 fases.
