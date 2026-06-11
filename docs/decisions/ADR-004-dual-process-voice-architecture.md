# ADR-004: Arquitectura dual-process (race-core + voice-brain)

## Status

**Revised (ADR-004-R1)** — 2026-06-07 tras revisión multi-modelo (3/3). Fase 2 original **retirada**; ver [síntesis](../architecture/adr-004-multi-model-synthesis.md).

## Date

2026-06-07 (R1: mismo día)

## Context

Vantare debe alcanzar **paridad funcional con CrewChief** implementada **nativamente** (`crewchief_events/`, spotter, strategy), sin ejecutar CrewChiefV4. Prioridad del producto: **estabilidad en pista** (spotter + ingeniero audible) antes que nuevas features.

El monolito actual (FastAPI + Tauri + audio en React) concentra demasiados subsistemas en un proceso y reparte el audio entre frontend y backend. Fallos observados en producción: desync de config, TTS silenciado por gates frontend, deploy PyInstaller frágil, evaluación CC ligada al WebSocket por cliente.

Este ADR consolida cinco análisis previos a la decisión y define el checklist de migración.

---

## Análisis 1 — Comparativa de arquitecturas

| Opción | Fiabilidad | Paridad CC nativa | Esfuerzo | Veredicto |
|--------|------------|-------------------|----------|-----------|
| **A. Monolito actual** (1 proceso Python + audio React) | Baja | En curso (~25 módulos CC) | 0 (status quo) | ❌ Rechazar — fallos recurrentes |
| **B. Monolito + audio worker** (1 exe, cola interna; opcional `multiprocessing`) | Alta | ✅ Compatible | Medio (1–3 sem) | ✅ **Elegida (R1)** |
| **B-old. Dual-process + WS + supervisor.ps1** | Media | Compatible | Medio | ❌ Retirada (3/3 revisiones) |
| **C. CC headless como motor** | Muy alta en carrera | 100% CC determinista | Alto (fork C#) | ❌ Rechazada — producto no quiere depender de CC |
| **D. Reescritura race-core Rust/C#** | Muy alta | Reimplementar años | Muy alto | ❌ Posponer — solo si B falla en telemetría |
| **E. 3+ procesos** (telemetry / race / voice / UI) | Media-alta | Compatible | Alto (IPC) | ❌ Rechazada — más ops sin ganancia clara vs B |

**Conclusión:** Para paridad CC **sin** usar CC, **B** es el mejor equilibrio fiabilidad/esfuerzo/reutilización de código existente.

---

## Análisis 2 — Modos de fallo (actual vs objetivo)

| Modo de fallo | Hoy | Con ADR-004 |
|---------------|-----|-------------|
| LLM bloquea / cuelga event loop | Posible (mismo proceso) | Aislado en voice-brain |
| Crash TTS / Edge API | Frontend deja de hablar | voice-brain reinicia; race-core sigue |
| `spotterEnabled` desync UI/backend | Observado | Config ACK + voice-brain ignora gate UI spotter |
| `ReferenceError` / bug en `ttsPipeline.ts` | Silencio total TTS | Backend es único reproductor |
| PyInstaller bytecode ≠ `_internal/src` | Deploy parcial roto | Fase 3: python-embed |
| CC `on_frame` solo si hay WS conectado | **Bug arquitectónico** (`telemetry_sender_loop` por cliente) | race-core: un loop global 20 Hz |
| Spotter global + CC por WS | Doble path telemetría | Un tick → spotter + suite CC |
| Múltiples clientes WS duplican CC | Sí | race-core evalúa una vez |
| Reconnect WS pierde audio en cola | Observado | Cola en voice-brain persiste |

**Conclusión:** ADR-004 elimina los fallos **estructurales** ya reproducidos; no elimina bugs lógicos en módulos CC (requieren tests de paridad).

---

## Análisis 3 — Compatibilidad con paridad CrewChief nativa

| Componente CC en Vantare | Ubicación | Destino en ADR-004 |
|--------------------------|-----------|-------------------|
| 25 módulos `crewchief_events/modules/*` | Python | **race-core** (sin cambio de lógica) |
| `CrewChiefGameStateLoop` + `DelayedMessageQueue` | Python | **race-core** — mover fuera de WS |
| `SpotterService` + geometry | Python | **race-core** — mismo tick que CC |
| `playback.py` / prioridades | Python | **voice-brain** (cola + play) |
| `VerbosityController` | Python | **race-core** filtra; voice-brain respeta |
| `cutover_registry` | Python | Mantener hasta retirar legacy |
| LLM PTT / triggers | `engine.py` | **voice-brain** (slow path) |
| `ProactiveMonitorSuite` legacy | Python | **Eliminar** tras cutover pearls |
| `CommentaryOrchestrator` batch | Python | **Desactivar release** — CC es path proactivo |
| Frontend `priorityAudioQueue` | TS | **Eliminar** del path crítico |
| Ducking WASAPI | Tauri Rust | Mantener — invocado desde voice-brain vía IPC mínimo |

**Conclusión:** La paridad CC **no compite** con ADR-004; la **refuerza** al unificar evaluación y playback bajo reglas CC (`docs/architecture/pipelines/04-playback-moderator.md`).

---

## Análisis 4 — Coste y simplicidad

| Métrica | Monolito | ADR-004 |
|---------|----------|---------|
| Procesos runtime | 2 (Tauri + Python) | 3 (Tauri + race-core + voice-brain) |
| Saltos alerta → oído | 6+ | 2 |
| Loops 20 Hz en race path | 2–3 (spotter global + telemetry WS × N) | **1** |
| Backends TTS activos (release) | 4 | **1** (Edge) |
| Líneas a mover/crear (estimado) | — | ~800–1500 (voice service + IPC + supervisor) |
| Código CC a reescribir | — | **0** (reorganizar, no reimplementar) |

**Trade-off aceptado:** +1 proceso Python a cambio de aislar slow path y unificar audio.

**Trade-off rechazado:** Rust race-core ahora (+6–12 meses) sin evidencia de que Python 20 Hz sea el cuello (telemetry reader ya es nativo C).

---

## Análisis 5 — ¿Por qué no quedarnos en monolito “arreglado”?

Incluso con P0 (`config_ack`, defaults spotter, fix `ttsPipeline`) el monolito conserva:

1. **Dos dueños de audio** (React + `/tts`) — cualquier bug frontend = silencio.
2. **Evaluación CC acoplada al WS** — sin UI conectada, CC no corre (`websocket.py:167-177`).
3. **Competición LLM ↔ spotter** en el mismo event loop.
4. **PyInstaller** como único artefacto de backend.

Parches P0 son **necesarios pero insuficientes** para “mayor seguridad de no tener fallos”.

---

## Decision (R1 — post revisión multi-modelo)

Adoptar **monolito de despliegue** (un `backend.exe`) con separación **lógica** race-core / audio-worker:

```
LMU shared memory
       │
       ▼
┌──────────────────────────────────────────┐
│ backend.exe (PyInstaller, UN despliegue)  │
│                                          │
│  race-core (async principal)             │
│  • TelemetryReader + StrategyService     │
│  • race_tick_loop 20 Hz GLOBAL           │
│  • spotter + CrewChiefEventSuite         │
│  • DelayedMessageQueue + is_message_     │
│    still_valid (ANTES de encolar audio)  │
│  • IntelligenceEngine + LLM + RAG        │
│  • Emite PlayCommand → cola interna      │
│  • WS/UI: telemetría ~10 Hz              │
│                                          │
│       │ asyncio.Queue (Fase 1)           │
│       │ multiprocessing.Queue (Fase 2-R1 │
│       │   solo si evidencia GIL/CPU)     │
│       ▼                                  │
│  audio-worker (in-process o Process hijo)│
│  • TTS (Edge + pre-cache spotter)        │
│  • sounddevice + pycaw ducking           │
│  • Whisper bajo PTT                      │
│  • Cola reproducción IMMEDIATE > NORMAL  │
└─────────────────┬────────────────────────┘
                  │ WS mínimo (UI, PTT stream)
                  ▼
┌──────────────────────────────────────────┐
│ Tauri + React (solo UI)                  │
│ • Sin GET /tts path crítico              │
│ • PTT: stream PCM (no WAV POST)          │
│ • Spawn/kill UN backend.exe              │
└──────────────────────────────────────────┘
```

**Retirado en R1:** `supervisor.ps1`, dos exe independientes, IPC WebSocket localhost, LLM en proceso de voz separado.

### Contrato `PlayCommand` (reemplaza VoiceEvent para audio)

```json
{
  "id": "uuid",
  "ts": 1717777777.123,
  "text": "Coche a la izquierda",
  "wav_cache_key": "spotter_left",
  "priority": "IMMEDIATE",
  "category": "spotter",
  "ttl_ms": 2000
}
```

`wav_cache_key` opcional — spotter usa cache local (<100 ms); texto dinámico va a Edge TTS.

### Reglas invariantes (R1)

1. **Un snapshot por tick** — `StrategyService.snapshot_frame()` alimenta spotter y CC.
2. **Un evaluador global** — nunca por conexión WebSocket.
3. **Validación CC antes de audio** — `is_message_still_valid` en race-core, no en el worker.
4. **LLM permanece en race-core** — acceso directo a StrategyService y telemetría.
5. **Un reproductor** — sounddevice en audio-worker; frontend no usa HTMLAudioElement.
6. **Un exe en release** — Tauri lifecycle; `multiprocessing.freeze_support()` si hay Process hijo.
7. **Release slim** — Edge TTS + pre-cache spotter; ChromaDB/MQTT/traces off.

### Fase 2-R1 (condicional)

Separar **solo el audio-worker** con `multiprocessing.Process` **dentro del mismo exe** si métricas de pista muestran contention CPU/GIL. **No** dos servicios + red localhost.

---

## Decision (original — superseded)

<details>
<summary>Texto original ADR-004 (dual-process + supervisor.ps1) — histórico</summary>

Adoptar arquitectura **dual-process Python + UI Tauri**:

```
LMU shared memory
       │
       ▼
┌──────────────────────────────────────────┐
│ race-core (FastAPI ligero o uvicorn app) │
│ • TelemetryReader + StrategyService      │
│ • UN loop 20 Hz: spotter + CC suite      │
│ • Emite VoiceEvent → localhost queue     │
│ • WS/UI: telemetría 10 Hz, config, health│
└─────────────────┬────────────────────────┘
                  │ VoiceEvent (JSON/TCP/WS)
                  ▼
┌──────────────────────────────────────────┐
│ voice-brain (proceso Python separado)    │
│ • Cola priorizada (IMMEDIATE > NORMAL)   │
│ • Edge TTS + sounddevice                 │
│ • Whisper PTT + LLM stream               │
│ • Ducking vía invoke Tauri (IPC)         │
└─────────────────┬────────────────────────┘
                  │ HTTP mínimo (health, PTT upload)
                  ▼
┌──────────────────────────────────────────┐
│ Tauri + React (solo UI)                  │
│ • Sin GET /tts en path crítico           │
│ • PTT: WAV → POST                        │
│ • Mute global / volumen                  │
└──────────────────────────────────────────┘

supervisor.ps1: reinicia voice-brain; opcional race-core
```

### Contrato `VoiceEvent` (mínimo)

```json
{
  "id": "uuid",
  "ts": 1717777777.123,
  "text": "Coche a la izquierda",
  "priority": "IMMEDIATE",
  "category": "spotter",
  "channel": "spotter",
  "ttl_ms": 2000,
  "play_even_in_hard_parts": false
}
```

### Reglas invariantes

1. **Un snapshot por tick** — `StrategyService.snapshot_frame()` alimenta spotter y `CrewChiefGameStateLoop`.
2. **Un evaluador global** — nunca por conexión WebSocket.
3. **Un reproductor** — `sounddevice` en voice-brain; frontend no usa `HTMLAudioElement` para ingeniero/spotter.
4. **Slow path aislado** — LLM/TTS/Whisper nunca en race-core.
5. **Release slim** — Edge TTS only; ChromaDB/MQTT/traces off.

</details>

---

## Alternatives Considered

Ver Análisis 1 y [síntesis multi-modelo](../architecture/adr-004-multi-model-synthesis.md). R1 (monolito + audio worker) supera B-old en fiabilidad/operabilidad; Fase 2-R1 (`multiprocessing`) queda como escape hatch.

---

## Consequences

### Positivas

- Spotter y CC corren **siempre**, con o sin UI.
- Fallos de voz no tumban telemetría.
- Playback alineado con `PlaybackModerator` CC en un solo sitio.
- Tests de contrato más simples (race-core emite evento → voice-brain ACK/play).

### Negativas

- Worker CPU-bound (Whisper/Piper) puede competir con tick 20 Hz en un solo proceso — mitigar con Fase 2-R1 condicional.
- Pre-cache spotter y decode MP3→PCM añaden trabajo en Fase 1b.
- Migración incremental — convivencia temporal con frontend TTS durante Fase 1.

### Follow-up

- Síntesis revisiones: [`../architecture/adr-004-multi-model-synthesis.md`](../architecture/adr-004-multi-model-synthesis.md)
- Implementación: [`../architecture/dual-process-consolidation-checklist.md`](../architecture/dual-process-consolidation-checklist.md)
- Actualizar `docs/arquitectura-shell-desktop.md` tras Fase 1.
- ADR-005 (futuro): python-embed vs PyInstaller si Fase 3 confirma deuda.

---

## Validación de la decisión (criterios de aceptación)

| # | Criterio | Cómo verificar |
|---|----------|----------------|
| V1 | Spotter audible con UI cerrada | backend.exe solo + audio-worker; p95 <500 ms (cache <100 ms) |
| V2 | CC suite corre sin WS | Integration test: loop global |
| V3 | Crash audio-worker → race-core sigue | Kill worker thread/Process; tick loop OK |
| V4 | Un cliente vs tres clientes WS → misma cantidad eval CC | Test contador `on_frame` |
| V5 | PTT no bloquea spotter > 500 ms | Latency test bajo carga LLM |
| V6 | Deploy script < 2 min, verificable | `doctor.ps1` green |

Si V1–V4 fallan tras Fase 1, corregir antes de separar procesos. Fase 2-R1 solo con evidencia CPU/GIL en pista.
