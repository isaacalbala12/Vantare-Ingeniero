# Checklist — Consolidación ADR-004-R1 (monolito + audio worker)

> **ADR:** [ADR-004](../decisions/ADR-004-dual-process-voice-architecture.md) (R1)  
> **Síntesis:** [adr-004-multi-model-synthesis.md](adr-004-multi-model-synthesis.md)  
> **Objetivo:** Un cerebro de carrera + un dueño de audio, paridad CC nativa, **un exe** en release.

---

## Estado actual (deuda detectada en código)

| Problema | Evidencia | Severidad |
|----------|-----------|-----------|
| CC evalúa **por cliente WS** | `websocket.py` → `telemetry_sender_loop` llama `crewchief_loop.on_frame` | **P0** |
| Spotter evalúa **global** pero CC no | `spotter_eval_loop` vs `on_frame` en WS | **P0** |
| Dos paths de emisión de voz | `emit_crewchief_messages` + spotter alerts + commentary | P1 |
| Audio en frontend | `priorityAudioQueue.ts`, `ttsPipeline.ts`, `GET /tts` | P1 |
| `broadcast_sync` fire-and-forget | `websocket.py:broadcast_sync` | P2 |
| 4 TTS en lifespan | `main.py` steps 7–10 | P2 |
| ChromaDB en lifespan release | `main.py` EventStore | P3 |

---

## Fase 0 — Cerrar bugs estructurales en monolito (1–2 días)

Pre-requisito antes de separar procesos; reduce ruido al migrar.

- [ ] **0.1** Extraer `race_tick_loop(app_state)` global 20 Hz en `backend/src/race/tick_loop.py`
  - Mueve lógica de `spotter_eval_loop` + `crewchief_loop.on_frame` aquí
  - **Elimina** `crewchief_loop.on_frame` de `telemetry_sender_loop`
- [ ] **0.2** `telemetry_sender_loop` solo envía bytes UI (throttle **10 Hz** configurable)
- [ ] **0.3** Test: `test_race_tick_single_eval_per_tick.py` — N clientes WS → 1 eval CC por tick
- [ ] **0.4** Test: CC + spotter corren con `active_connections == 0`

**Archivos:** `routers/websocket.py`, `main.py`, nuevo `race/tick_loop.py`

---

## Fase 1 — audio-worker in-process (4–6 días)

Mismo proceso, cola dedicada + reproducción backend — valida contrato antes de cualquier `multiprocessing`.

### 1a — Reproducción backend

- [ ] **1.1** Crear `backend/src/voice/service.py` — cola reproducción IMMEDIATE > NORMAL
- [ ] **1.2** Crear `PlayCommand` pydantic en `models/play_command.py`
- [ ] **1.3** race-core emite `PlayCommand` **después** de `is_message_still_valid` / DelayedQueue
- [ ] **1.4** Redirigir spotter + `emit_crewchief_messages` → `voice_service.enqueue`
- [ ] **1.5** Flag `VOICE_BACKEND_PLAYBACK=1`; frontend no llama `/tts` para alert/commentary
- [ ] **1.6** WS `event=alert` solo para subtítulos UI
- [ ] **1.7** `sounddevice` + `asyncio.to_thread`; fallback frontend si falla init
- [ ] **1.8** **pycaw** ducking en mismo hilo que playback (retirar ducking async Tauri del path crítico)

### 1b — Latencia spotter + PTT

- [ ] **1.9** Pre-cache WAV/MP3 frases spotter fijas (~50) al arranque (estilo CC sound files)
- [ ] **1.10** `PlayCommand.wav_cache_key` para spotter; Edge TTS solo texto dinámico
- [ ] **1.11** PTT: stream PCM por WS (no WAV POST) o capture PTT en backend (`pynput` + hotkey)
- [ ] **1.12** Test: p95 spotter cache <100 ms; p95 Edge dinámico documentado

**Archivos:** `voice/`, `spotter.py`, `engine.py`, `delayed_queue.py`, `config.py`, `frontend/useWebSocket.ts`

---

## Fase 2-R1 — multiprocessing condicional (solo con evidencia)

**Gate:** p95 tick >40 ms OR crash por Whisper/Piper OR tick <18 Hz bajo carga — medido en pista post Fase 1.

- [ ] **2.1** `multiprocessing.Process` audio-worker, **mismo** PyInstaller bundle
- [ ] **2.2** `multiprocessing.Queue` para `PlayCommand` (+ `freeze_support()` en entrypoint)
- [ ] **2.3** LLM **permanece** en proceso principal (race-core)
- [ ] **2.4** Tauri sigue spawnando **un** exe; el exe fork interno del worker

~~Fase 2-old (retirada):~~ ~~2 exe + WS localhost + supervisor.ps1~~

---

## Fase 2-old — RETIRADA (referencia histórica)

<details>
<summary>Fase 2 original ADR-004 — no implementar</summary>

- ~~race_core_main.py + voice_brain_main.py separados~~
- ~~IPC WebSocket localhost:8009~~
- ~~supervisor.ps1~~

</details>

---

## Fase 3 — slim release (post-beta, 3–4 días)

### Un solo cerebro de eventos

- [ ] **3.1** Confirmar `cutover_registry` cubre todos los eventos proactivos activos
- [ ] **3.2** Desactivar `CommentaryOrchestrator` en release (`COMMENTARY_BATCH=0`)
- [ ] **3.3** Retirar emisiones legacy en `ProactiveMonitorSuite` (ya vacío post-Task 48)
- [ ] **3.4** Documentar en `cutover_registry` eventos restantes sin módulo CC

### Un solo path de audio

- [ ] **3.5** Eliminar `createTtsPipeline` del path alert/commentary (mantener solo dev fallback)
- [ ] **3.6** Eliminar `evaluateAlertTts` gates spotter (solo mute global + `engineerEnabled`)
- [ ] **3.7** Retirar SpeechRecognition web; PTT solo Whisper
- [ ] **3.8** Un TTS en release: `TTS_BACKEND=edge`

### Infra release

- [ ] **3.9** ChromaDB / MQTT / trace playback detrás de `DEBUG_FEATURES=1`
- [ ] **3.10** `doctor.ps1`: health race-core + voice-brain + test TTS + test VoiceEvent roundtrip
- [ ] **3.11** Evaluar python-embed vs PyInstaller (ADR-005 draft)

**Archivos:** `engine.py`, `commentary_orchestrator.py`, `frontend/services/*`, `main.py`, `config.py`

---

## Fase 4 — Validación paridad + estabilidad (continuo)

- [ ] **4.1** Smoke: 30 min sesión LMU — spotter lateral audible, sin UI conectada
- [ ] **4.2** `verify_voice_contract` pasa con `VOICE_BACKEND_PLAYBACK=1`
- [ ] **4.3** Matriz CC: módulos en `suite_factory.py` tienen test L1–L3 (`crewchief-pipeline-test-template.md`)
- [ ] **4.4** Kill voice-brain mid-session → supervisor restart < 3 s; race-core health OK
- [ ] **4.5** Métricas: p95 alerta→play < 500 ms (spotter), < 3 s (LLM PTT)

---

## Mapa de consolidación (qué fusionar)

```
ANTES (monolito)                    DESPUÉS (race-core)
─────────────────                   ────────────────────
spotter_eval_loop (global)    ──┐
telemetry_sender_loop CC      ──┼──► race_tick_loop @ 20Hz
strategy_sender engine cycle  ──┘    (una evaluación)

SpotterService._emit_alert    ──┐
emit_crewchief_messages       ──┼──► VoiceEvent → voice-brain
CommentaryOrchestrator (off)  ──┘

frontend priorityAudioQueue   ──X──► (eliminado path crítico)
frontend GET /tts             ──X──► voice-brain sounddevice
```

---

## Qué NO tocar en esta migración

- `shared-telemetry/` — lectura nativa (ADR-003)
- `shared-strategy/` — motores de estrategia
- Lógica en `crewchief_events/modules/*` — solo cambia **quién llama** y **dónde suena**
- `spotter_geometry.py`, `cartesian_spotter.py` — detección ya validada en backend
- Protocolo WS telemetría MessagePack — solo bajar frecuencia UI

---

## Orden de ejecución recomendado

```
Fase 0  →  Fase 1a  →  Fase 1b  →  Fase 4 (smoke)  →  [Fase 2-R1 si métricas]  →  Fase 3
  │            │           │              │
  │            │           │              └─ beta en pista
  │            │           └─ pre-cache spotter + PTT stream
  │            └─ sounddevice + pycaw in-process
  └─ race_tick_loop global (P0)
```

**Quick win inmediato:** Fase 0.1–0.4 (un loop global) — mejora estabilidad CC **sin** esperar voice-brain.

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| sounddevice bloquea event loop | `asyncio.to_thread` + cola única |
| Dos procesos complican debug | `scripts/dev-dual.ps1` + logs separados |
| Regresión paridad CC | No cambiar módulos; solo wiring; tests existentes |
| Tauri no recibe eventos LLM | voice-brain mantiene WS secundario solo para UI tokens |
| Latencia IPC | localhost; batch no necesario para <100 eventos/min |

---

## Definition of Done (proyecto)

- [ ] ADR-004 criterios V1–V6 verdes
- [ ] Documentación `arquitectura-shell-desktop.md` actualizada
- [ ] Instalador spawnea race-core + voice-brain + Tauri
- [ ] Usuario reporta spotter audible en pista ≥ 3 sesiones consecutivas sin intervención manual de toggles
