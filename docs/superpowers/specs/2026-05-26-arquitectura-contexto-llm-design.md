# 🏎️ Vantare Ingeniero IA — Diseño de Arquitectura: Contexto de Carrera para el LLM

**Fecha**: 2026-05-26
**Estado**: Diseño validado, pendiente de implementación

---

## 1. Visión general

El Ingeniero de IA de Vantare es un sistema distribuido en 2 PCs:

| PC | Rol | Componentes |
|----|-----|------------|
| **Windows** (cliente) | Juego + Estrategia + Spotter | LMU, Tauri Frontend, TelemetryReader, StrategyService, StateChangeDetector, SpotterService |
| **Linux** (servidor) | LLM + TTS + Historial | Qwen 3.5 4B (Hipfire), Edge TTS, ChromaDB, RAG (multilingual-e5-large) |

El LLM recibe el **contexto completo de carrera** para razonar tácticamente, sin que el motor determinista pre-dirija sus conclusiones.

---

## 2. Tres capas de transporte de contexto

### Capa 2.1: Transporte (MessagePack + Delta Encoding)

```
Frontend Windows → Backend Linux (WebSocket)
  - Snapshot completo cada 5s (~300 bytes en MessagePack)
  - Delta frames entre medias (~20-50 bytes, solo campos cambiados)
  - Tráfico total: ~1 KB/s por cliente
  - 50 clientes simultáneos: ~50 KB/s en el servidor
```

**Librerías**: `msgpack` (Python), `@msgpack/msgpack` (TypeScript)

### Capa 2.2: Snapshot actual (Ticker compacto)

Formato simbólico ultra-compacto (~400 tokens para 40 rivales):

```
DRV:P3|L26|F:42.3L/3.2(13L)|TYR:72/68/65/63·92/94/98/96
BRK:38/35/22/20
GAP>VST:+2.1·1:48.2|<ALO:-1.2·1:47.9·d-0.3
SES:WEC|RACE|38L|45:22
WTH:PC|22°|R30%+15m|GRN|SC:N
RIV:VST|HY|+2.1|V22|78·ALO|HY|-1.2|--|65·LEC|HY|-5.4|V22|70·...
```

El LLM recibe un system prompt que le enseña a interpretar este formato. Todos los datos crudos, sin pre-digestión.

### Capa 2.3: Historial de carrera (RAG con embeddings)

```
┌─── Windows ─────────────────────────────────────┐
│  StateChangeDetector                             │
│    → Detecta eventos significativos por tick     │
│    → Guarda snapshots por vuelta por driver      │
│    → Envía al Linux vía WebSocket                │
└────────────────────┬─────────────────────────────┘
                     │ eventos + snapshots
                     ▼
┌─── Linux ───────────────────────────────────────┐
│  ChromaDB/LanceDB                                │
│    → Almacena eventos + snapshots                │
│    → multilingual-e5-large en CPU (2.2 GB RAM)   │
│    → Embedding: ~40ms (irrelevante, on-demand)   │
│    → Recupera top-5 eventos al trigger/pregunta  │
└─────────────────────────────────────────────────┘
```

**Modelo**: `multilingual-e5-large` (español + inglés, 2.2 GB en RAM, CPU)

**Datos almacenados**: ~400-600 eventos por carrera (~48 KB datos + ~3 MB índice vectorial)

---

## 3. Flujos separados: Spotter vs Inteligencia

### Spotter (20Hz, sin LLM)

```
TelemetryReader → SpotterService.evaluate_tick()
                      ↓
                 AlertMessage → WebSocket → TTS directo
                 
Ejemplos: "Pit limiter", "Coche detrás <0.5s", "Safety car", "Última vuelta"
```

En fase beta: AlertMessage → audio pregrabado (`.wav`). En alpha: TTS.

### Inteligencia (on-demand, con LLM)

```
Trigger automático O pregunta del piloto
        ↓
  Construir prompt (3 bloques):
    ┌─ System prompt (~200 tokens)
    ├─ Ticker compacto (~400 tokens, snapshot actual + 40 rivales)
    ├─ RAG top-5 eventos históricos (~100 tokens)
    └─ Trigger/pregunta (~30 tokens)
        ↓
  LLM (Qwen 3.5 4B, 1 sola inferencia)
        ↓
  AdviceEndMessage → WebSocket → TTS
```

---

## 4. StateChangeDetector (nuevo componente en Windows)

Detecta eventos significativos comparando frames consecutivos de telemetría:

| Tipo de evento | Disparador |
|---------------|-----------|
| `position_change` | Cambio de posición de cualquier driver |
| `pitstop` | Entrada/salida de boxes |
| `lap_completed` | Vuelta completada (agrupado cada 5 vueltas por driver) |
| `gap_change` | Gap entre 2 drivers cambia >0.3s |
| `safety_car` | SC/FCY activado/desactivado |
| `weather_change` | Cambio de clima/prob lluvia |
| `fastest_lap` | Vuelta rápida global/personal |
| `tyre_degradation` | Degradación acelera >20% vs media |

Cada evento genera un snapshot de vuelta con datos crudos (ritmo, desgaste, gaps, temperaturas).

---

## 5. LiveContextManager (extensión necesaria)

Actualmente solo guarda el estado actual en 3 tiers (FAST/STD/DEEP). Necesita extenderse para:

- Guardar snapshots históricos por vuelta por driver
- Exponer timeline de eventos para el RAG
- Mantener buffers de ritmo (últimas 5 vueltas por driver top-10)
- Mantener buffers de desgaste (últimas 5 vueltas propias)

---

## 6. Modelo LLM

- **Modelo**: Qwen 3.5 4B (base, no QwOPUS)
- **Motor**: Hipfire (Vulkan) en RX 6600 XT (8 GB VRAM)
- **Idioma**: Multilingüe (español + inglés)
- **Tool Calling**: Descartado (latencia extra, riesgo de alucinación en español). Se usa Progressive Disclosure en su lugar.
- **Soft Prompting**: Investigación futura (Fase 5+)

---

## 7. Pipeline de TTS

- **Alpha (actual)**: Edge TTS para todo (alertas + respuestas LLM)
- **Beta (futuro)**: AlertMessage → audio pregrabado (`.wav` local). Respuestas LLM → Edge TTS.
- **Latencia objetivo**: Spotter <100ms, Inteligencia ~2s

---

## 8. Windows Sidecar (Evolución)

| Fase | Implementación |
|------|---------------|
| **Alpha** | Proceso Python manual en Windows con shared-telemetry + shared-strategy |
| **Beta** | Tauri sidecar: Python empaquetado y gestionado por Tauri |

---

## 9. Lo que NO se implementa ahora

- Tool Calling con QwOPUS/Carnice (descartado por latencia y calidad español)
- Soft Prompting / Embedding Compression (investigación Fase 5+)
- Knowledge Graph (descartado por complejidad)
- Mover StrategyService a Rust (innecesario, sidecar Python es suficiente)

---

## 10. Referencias

- CrewChief V4: motor determinista C#, 40 eventos independientes, audios pregrabados, sin LLM
- Hipfire: https://github.com/Kaden-Schutt/hipfire
- multilingual-e5-large: https://huggingface.co/intfloat/multilingual-e5-large
- Qwen 3.5 4B: https://huggingface.co/Qwen/Qwen3-4B
