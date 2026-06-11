# Registro de decisiones — Re-arquitectura monolito + voz backend (2026-06-07)

> **Estado:** Acordado — listo para implementación  
> **Plan de ejecución:** [`../superpowers/plans/2026-06-07-monolith-voice-beta-rearchitecture.md`](../superpowers/plans/2026-06-07-monolith-voice-beta-rearchitecture.md)  
> **ADR vigente:** [ADR-004-R1](../decisions/ADR-004-dual-process-voice-architecture.md)

---

## 1. Contexto del producto

**Vantare Ingeniero IA** — app desktop Windows para **Le Mans Ultimate (LMU)**:

- Ingeniero de pista + **spotter por voz** en español
- **PTT** conversacional con LLM
- **Paridad funcional CrewChief** implementada **nativamente** en Python (`crewchief_events/`, ~25 módulos)
- **No** usar CrewChiefV4 como runtime/dependencia

**Prioridades de negocio:**

1. Estabilidad en pista (spotter + ingeniero **audibles**)
2. Lanzar beta estable **pronto** (equipo pequeño, ~1 año de código)
3. Corregir arquitectura de verdad, no solo parches frontend

---

## 2. Problemas observados (síntomas confirmados)

| ID | Problema | Evidencia |
|----|----------|-----------|
| P0 | CC evalúa **por cliente WebSocket** | `websocket.py:167-177` — `crewchief_loop.on_frame` dentro de `telemetry_sender_loop` |
| P0 | Spotter global, CC no | `spotter_eval_loop` en `main.py` vs CC en WS |
| P0 | CC **no corre sin UI** conectada | Mismo bug WS |
| P0 | N clientes WS **duplican** eval CC | Un loop por conexión |
| P1 | Spotter en logs backend, **inaudible** | Desync config, gates frontend, bugs `ttsPipeline.ts` |
| P1 | Audio repartido React + Python | `GET /tts`, `HTMLAudioElement`, `priorityAudioQueue.ts` |
| P1 | Un bug TS = silencio total TTS | `ReferenceError` en pipeline documentado |
| P2 | PyInstaller deploy frágil | Copias parciales, bytecode vs `_internal/src` |
| P2 | LLM/TTS compiten con telemetría 20 Hz | Mismo proceso/event loop sin fronteras |

---

## 3. Cronología de análisis

### 3.1 Análisis interno (Cursor / ADR-004 original)

- Propuesta inicial: **dual-process** (`race-core` + `voice-brain`) + IPC WebSocket + `supervisor.ps1`
- Identificado bug P0 CC-on-WS
- Checklist fases 0–4

### 3.2 Revisión multi-modelo ADR (3 modelos, prompt ADR)

| Modelo | Veredicto Fase 2 (2 exe + WS + PS) | Consenso |
|--------|-------------------------------------|----------|
| Análisis 1 (devil's advocate) | ❌ Rechazar → `multiprocessing` mismo exe | Fase 0+1 sí |
| Análisis 2 | ⚠️ Condicional a evidencia | Fase 1 = 80% valor |
| Análisis 3 | ❌ Rechazar distribuida | Monolito multiproceso |

**Síntesis:** [`adr-004-multi-model-synthesis.md`](adr-004-multi-model-synthesis.md)

### 3.3 Diseño abierto (2 modelos, sin plan previo)

| Tema | Modelo 1 | Modelo 2 | Consenso |
|------|----------|----------|----------|
| Procesos beta | 1 exe monolito | 1 exe monolito | **3/3** |
| Audio | Backend sounddevice | Backend pygame.mixer beta | **Backend, no React** |
| race_loop global | Sí | Sí | **Unánime** |
| Pre-cache spotter | Sí | Sí (~50 frases) | **Unánime** |
| LLM ubicación | race-core | Mismo proceso async | **Unánime** |
| Validación CC | Antes de play, con telemetría | PlaybackModerator (corregido) | **Validar en race path antes de encolar** |
| Ducking | pycaw sync con play | pycaw + fallback Tauri | **pycaw primero** |
| RAG/ChromaDB | Post-beta | Post-beta | **Fuera de beta** |
| Split procesos | Solo si GIL/CPU | Solo si métricas | **Condicional post-beta** |

**Mejor trabajo plan ejecutable:** Modelo 2  
**Mejor fundamentos CC/validación:** Modelo 1  
**Decisión:** Roadmap Modelo 2 + reglas validación Modelo 1

---

## 4. Arquitectura acordada — ADR-004-R1

### 4.1 Principio rector

> **Monolito disciplinado** con fronteras internas claras.  
> **Segmentación quirúrgica** solo si métricas en pista lo exigen — no por calendario.

No es: monolito caótico actual → microservicios locales  
Es: monolito ordenado → opcional `multiprocessing.Process` para audio/ML

### 4.2 Diagrama objetivo (beta)

```
LMU shared memory
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│ backend.exe (PyInstaller --onedir, UN despliegue)         │
│                                                          │
│  race_loop @ 20 Hz (GLOBAL, lifespan singleton)          │
│    1. snapshot = strategy.snapshot_frame()               │
│    2. spotter.evaluate_tick(snapshot)                    │
│    3. crewchief_loop.on_frame(snapshot)                  │
│    4. delayed_queue + is_message_still_valid → emit      │
│                                                          │
│  voice_loop (asyncio, mismo proceso)                     │
│    • asyncio.Queue[PlayCommand]                          │
│    • pre-cache spotter WAV                               │
│    • Edge TTS (ingeniero) / pygame.mixer play            │
│    • pycaw ducking (fallback Tauri)                      │
│                                                          │
│  strategy_loop @ 0.5 Hz (existente StrategyService)      │
│  LLM PTT → asyncio.Task (nunca bloquea race_loop)        │
│                                                          │
│  FastAPI /ws → telemetría UI ~10 Hz (TelemetryHub)       │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│ Tauri + React — UI pasiva en carrera                       │
│ • Overlay/subtítulos (AlertMessage WS)                     │
│ • Config + config_ack                                      │
│ • PTT → texto por WS (Web Speech API beta)                 │
│ • NO reproduce audio spotter/ingeniero                     │
│ • Spawn/kill UN backend.exe                                │
└──────────────────────────────────────────────────────────┘
```

### 4.3 Invariantes (no negociables)

1. **Un snapshot por tick** — spotter y CC leen el mismo frame
2. **Un evaluador global** — nunca por conexión WebSocket
3. **`is_message_still_valid` antes de encolar audio** — con `CrewChiefFrameContext` en race path
4. **LLM en race-core** — acceso directo a `StrategyService`; nunca en proceso de voz separado
5. **Un reproductor** — backend; frontend solo subtítulos
6. **Un exe en release** — Tauri lifecycle
7. **Release slim** — Edge TTS + pre-cache spotter; ChromaDB/MQTT/Commentary batch off

### 4.4 Contratos internos

**PlayCommand** (cola de voz, interno):

```python
@dataclass(frozen=True)
class PlayCommand:
    id: str
    text: str
    priority: Literal["IMMEDIATE", "NORMAL", "ENGINEER"]
    category: str  # spotter | engineer | pearl | ...
    event_id: str
    ttl_ms: int
    wav_cache_key: str | None = None
    expires_at: float  # time.monotonic() + ttl
```

**AlertMessage** (WebSocket → UI): se mantiene para overlay; no dispara TTS en frontend cuando `voiceBackendPlayback=true`.

### 4.5 Retirado explícitamente

- ❌ 2 exe + IPC WebSocket localhost + `supervisor.ps1`
- ❌ LLM en voice-brain separado
- ❌ Audio crítico en `HTMLAudioElement`
- ❌ Fase 2 como camino crítico a beta

### 4.6 Gate Fase 2-R1 (post-beta, condicional)

Activar `multiprocessing.Process` **solo audio-worker** (mismo exe) si:

- p95 `race_loop` > 40 ms en pista, o
- tick rate < 18 Hz bajo carga TTS/LLM, o
- crash repetido atribuible a Whisper/Piper local

---

## 5. Scope beta vs post-beta

### Beta incluye

- ✅ `race_loop` global + tests sin WS
- ✅ `voice_loop` + backend reproduce audio
- ✅ Pre-cache spotter (<100 ms p95)
- ✅ CC suite completa (25 módulos)
- ✅ PTT + LLM streaming
- ✅ Overlay visual (red de seguridad)
- ✅ `config_ack` + toggles
- ✅ Ducking (pycaw o fallback Tauri)
- ✅ `doctor.ps1`
- ✅ Edge TTS + fallback Piper offline

### Beta excluye

- ❌ LLM proactivo no solicitado (`CommentaryOrchestrator` off)
- ❌ ChromaDB / RAG
- ❌ MQTT
- ❌ Whisper ASR backend (Web Speech en beta)
- ❌ Traces/replay producción
- ❌ ElevenLabs / Gemini TTS
- ❌ Multi-proceso (salvo gate métricas)
- ❌ Comandos voz grammar CC

---

## 6. Criterios de aceptación (V1–V6)

| ID | Criterio | Verificación |
|----|----------|--------------|
| V1 | Spotter audible UI cerrada | backend solo + audio; p95 cache <100 ms |
| V2 | CC corre sin WS | test integración 60 s mock telemetría |
| V3 | Crash voice_loop → race_loop OK | kill task; `/health` tick alive |
| V4 | N clientes WS = 1 eval/tick | test contador |
| V5 | PTT no bloquea spotter >500 ms | test jitter race_loop bajo PTT |
| V6 | Deploy verificable | `doctor.ps1` green <2 min |

---

## 7. Mapa de archivos (plan completo)

| Acción | Ruta |
|--------|------|
| Create | `backend/src/race/tick_loop.py` |
| Create | `backend/src/race/telemetry_hub.py` |
| Create | `backend/src/voice/play_command.py` |
| Create | `backend/src/voice/voice_queue.py` |
| Create | `backend/src/voice/moderator.py` |
| Create | `backend/src/voice/bridge.py` |
| Create | `backend/src/voice/tts_manager.py` |
| Create | `backend/src/voice/spotter_cache.py` |
| Create | `backend/src/voice/player_pygame.py` |
| Create | `backend/src/voice/ducking.py` |
| Create | `backend/src/voice/service.py` |
| Modify | `backend/src/main.py` |
| Modify | `backend/src/routers/websocket.py` |
| Modify | `backend/src/config.py` |
| Modify | `backend/src/intelligence/engine.py` |
| Modify | `backend/src/intelligence/spotter.py` |
| Modify | `backend/src/routers/health.py` |
| Modify | `backend/pyproject.toml` |
| Modify | `frontend/src/store/config.ts` |
| Modify | `frontend/src/hooks/useWebSocket.ts` |
| Modify | `frontend/src/services/ttsPlaybackGate.ts` |
| Create | `scripts/doctor.ps1` |
| Tests | `backend/tests/test_race_tick_loop.py`, `test_voice_*.py` |

---

## 8. Riesgos priorizados y mitigaciones

| Sev | Riesgo | Mitigación |
|-----|--------|------------|
| P0 | CC-on-WS persiste | Task 1 plan: `race_loop` + eliminar L167-177 |
| P0 | GIL bloquea ticks | `asyncio.to_thread` TTS; ProcessPool post-beta |
| P1 | Edge TTS lento spotter | Pre-cache WAV al arranque |
| P1 | pygame falla en algunos PCs | doctor.ps1 + fallback playsound |
| P1 | pycaw no duck LMU | fallback Tauri `duck_lmu` |
| P2 | Regresión CC paridad | snapshots `.bin` + tests regresión |

---

## 9. Preguntas abiertas (resolver durante implementación)

1. Latencia Edge TTS desde región usuario → medir en Task pre-cache
2. LMU WASAPI shared vs exclusive → afecta ducking
3. `multiprocessing.freeze_support()` si activamos Fase 2-R1
4. Web Speech API en build instalado vs streaming PCM fallback

---

## 10. Documentos relacionados

| Documento | Propósito |
|-----------|-----------|
| [ADR-004-R1](../decisions/ADR-004-dual-process-voice-architecture.md) | Decisión arquitectónica |
| [adr-004-multi-model-synthesis.md](adr-004-multi-model-synthesis.md) | Síntesis 3 revisiones ADR |
| [dual-process-consolidation-checklist.md](dual-process-consolidation-checklist.md) | Checklist (actualizar al cerrar plan) |
| [prompt-open-architecture-design.md](prompt-open-architecture-design.md) | Prompt diseño abierto |
| [prompt-multi-model-adr-review.md](prompt-multi-model-adr-review.md) | Prompt revisión ADR |
| [crewchief-comparison.md](../crewchief-comparison.md) | Paridad CC referencia |
| [voice-contract.md](../voice-contract.md) | Contrato voz existente |

---

## 11. Cómo proseguir

1. Ejecutar plan: [`2026-06-07-monolith-voice-beta-rearchitecture.md`](../superpowers/plans/2026-06-07-monolith-voice-beta-rearchitecture.md)
2. Tras Hito 1 (race_loop): smoke backend sin UI — logs CC @ 20 Hz
3. Tras Hito 3 (voice_loop): spotter audible en dev
4. Tras Hito 5 (slim + doctor): candidato beta instalador
5. 30 min pista LMU → medir V1–V6 → decidir Fase 2-R1

**No iniciar** split de procesos hasta evidencia de métricas.
