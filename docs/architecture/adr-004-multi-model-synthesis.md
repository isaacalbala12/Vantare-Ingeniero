# Síntesis multi-modelo — ADR-004 (3 revisiones)

> **Fecha:** 2026-06-07  
> **Revisiones:** Análisis 1 (devil's advocate / multiprocessing), Análisis 2 (aprobar con cambios / Fase 2 condicional), Análisis 3 (rechazar Fase 2 distribuida / monolito multiproceso)

---

## Veredicto consolidado

| Modelo | ADR-004 original | Fase 0 | Fase 1 | Fase 2 (2 exe + WS + supervisor.ps1) |
|--------|------------------|--------|--------|--------------------------------------|
| Análisis 1 | Aprobar con **cambios mayores** | ✅ Urgente | ✅ Sí | ❌ **Rechazar** → `multiprocessing` |
| Análisis 2 | Aprobar con **cambios** | ✅ Imprescindible | ✅ 80% del valor | ⚠️ **Solo con evidencia** |
| Análisis 3 | **Rechazar** distribuida | ✅ Hoy | ✅ Sí | ❌ **Rechazar** → monolito multiproceso |

**Consenso:** **3/3** aprueban Fase 0 y Fase 1. **3/3** rechazan o posponen la Fase 2 tal como está escrita en ADR-004.

**Nueva arquitectura acordada:** **ADR-004-R1** — monolito de despliegue (1 exe PyInstaller) con **opcional** worker `multiprocessing` para CPU-bound (Piper/Whisper), no dos servicios + IPC de red + PowerShell.

---

## Tabla de consenso por tema

| Tema | A1 | A2 | A3 | Consenso | Acción |
|------|----|----|-----|----------|--------|
| Bug P0 CC en WS | ✅ | ✅ | ✅ | **Unánime** | Fase 0 ya |
| Fase 0 ship solo | Parcial | No (sin audio) | Parcial | Fase 0 **necesaria** pero **insuficiente** para “oír spotter” | 0 → 1 |
| Fase 1 resuelve ~80% dolor | Implícito | ✅ explícito | ✅ | **Unánime** | Prioridad beta |
| Fase 2 ADR original | ❌ | Condicional | ❌ | **Posponer** | Gate por métricas |
| supervisor.ps1 | ❌ | ⚠️ Tauri mejor | ❌ | **Evitar PS** | Tauri mata 1 exe |
| IPC localhost WS | ❌ | Named pipe si split | ❌ | **No WS** | Queue / pipe |
| LLM en voice-brain | ❌ | (en monolito) | ❌ | **LLM en race-core** | **Revisar ADR** |
| PlaybackModerator / `is_message_still_valid` | race-core | voice-brain ⚠️ | race-core | **2/3 race-core** | Mantener en race-core |
| Ducking | pycaw Python | Medir Tauri | pycaw Python | **pycaw + playback mismo hilo** | Mover de Tauri |
| Edge TTS spotter latencia | — | Pre-cache WAV | <100ms P95 | **Pre-cache frases fijas** | Nuevo ítem Fase 1 |
| PTT WAV POST | ❌ lento | — | ❌ streaming | **No POST blob final** | WS chunks o capture backend |
| Deploy 2 exes | ❌ | 1 bundle 2 stubs | ❌ | **1 exe** | ADR-R1 |
| PyInstaller + multiprocessing | freeze_support | — | ✅ | **Obligatorio en Windows** | Checklist Fase 1b |

---

## Contradicción resuelta: ¿Dónde vive PlaybackModerator?

**Análisis 2** ubica moderación en voice-brain (“como AudioPlayer thread de CC”).

**Análisis 1 y 3** (y el código) muestran que en Vantare la validación **no es solo cola**:

```89:99:backend/src/intelligence/crewchief_events/delayed_queue.py
def is_message_still_valid(
    message: CrewChiefMessage,
    ctx: CrewChiefFrameContext | None,
) -> bool:
    """Re-validación estilo Timings.cs:isMessageStillValid antes de hablar."""
    if ctx is None:
        return True
    key = message.validation_key or ""
    curr = ctx.current
    prev = ctx.previous or {}
```

`DelayedMessageQueue.ready()` necesita `CrewChiefFrameContext` con telemetría **en el tick de dequeue**. Eso exige:

| Capa | Responsabilidad |
|------|-----------------|
| **race-core** | Evaluar CC, hard-parts, delay, `is_message_still_valid`, prioridades, emitir `PlayCommand` ya validado |
| **audio-worker** | TTS (si hace falta), decode MP3→PCM, `sounddevice`, `pycaw` ducking, cola de **reproducción** (IMMEDIATE corta NORMAL) |

En CC real el AudioPlayer thread recibe mensajes **ya filtrados** por el game loop; la re-validación ocurre **antes** de inyectar el buffer. Vantare debe imitar eso: **moderación lógica en race-core**, **moderación acústica** (una sola salida, preemption) en el worker.

---

## ADR-004-R1 — Arquitectura revisada (consenso 3 modelos)

```
Tauri (UI)
  • Config, overlay, subtítulos
  • PTT → stream PCM (no WAV POST)
  • Sin HTMLAudioElement para ingeniero/spotter
  • Spawn: UN backend.exe, kill_on_drop
       │
       │ WS /health /config (solo UI)
       ▼
┌─────────────────────────────────────────────────────────┐
│ backend.exe (PyInstaller, un solo despliegue)            │
│                                                          │
│  [ Proceso/hilo principal — race-core lógico ]           │
│  • TelemetryReader + StrategyService                     │
│  • race_tick_loop @ 20 Hz (GLOBAL, no por WS)            │
│    1. snapshot_frame()                                   │
│    2. spotter.evaluate_tick()                            │
│    3. crewchief_loop.on_frame()                          │
│    4. DelayedMessageQueue + is_message_still_valid       │
│    5. emit PlayCommand → cola interna                    │
│  • IntelligenceEngine + LLM + RAG (slow, async tasks)    │
│  • FastAPI / WS telemetría ~10 Hz                        │
│                                                          │
│       │ asyncio.Queue o multiprocessing.Queue            │
│       ▼                                                  │
│  [ Audio worker — opcional Process si Piper/Whisper ]    │
│  • Consume PlayCommand { text | wav_cache_key, priority }│
│  • Edge TTS / cache spotter / Piper                      │
│  • sounddevice + pycaw (ducking síncrono al play)        │
│  • Whisper solo bajo PTT (ProcessPool si hace falta)     │
└─────────────────────────────────────────────────────────┘
```

### Fases revisadas

| Fase | Alcance | Beta crítica |
|------|---------|--------------|
| **0** | `race_tick_loop` global; sacar CC de WS | ✅ Sí |
| **1a** | `voice/service.py` in-process; backend reproduce; flag | ✅ Sí |
| **1b** | Pre-cache WAV spotter; pycaw; PTT streaming | ✅ Sí |
| **2-R1** | `multiprocessing.Process` audio worker **mismo exe** | Solo si cProfile/GIL |
| **2-OLD** | ~~2 exe + WS + supervisor.ps1~~ | ❌ **Retirado** |
| **3** | Slim release, retirar frontend TTS | Post-beta |
| **4** | Smoke LMU + V1–V6 | Continuo |

### Gates para activar Fase 2-R1 (multiprocessing)

Activar **solo si** tras Fase 1 en pista real:

- p95 `race_tick_loop` > 40 ms, o
- crash/restart del backend atribuible a Whisper/Piper, o
- tick rate cae bajo 18 Hz durante TTS/LLM

Sin evidencia → **no separar procesos**.

---

## Riesgos P0 unánimes (no cubiertos bien en ADR original)

1. **CC evaluado por cliente WS** — fix Fase 0  
2. **Procesos zombies + supervisor.ps1 + antivirus** — 1 exe, Tauri lifecycle  
3. **LLM sin StrategyService si vive en voice-brain** — LLM permanece en race-core  
4. **`is_message_still_valid` sin telemetría** — validación antes de PlayCommand  
5. **Edge TTS cloud >500 ms en spotter** — pre-cache frases fijas (estilo CC sound files)  
6. **Ducking Tauri async desincronizado** — pycaw en hilo de playback Python  

---

## Preguntas bloqueantes (priorizadas)

| # | Pregunta | Quién responde | Antes de |
|---|----------|----------------|----------|
| 1 | ¿p95 tick loop con Fase 1 in-process? | cProfile en sesión LMU | Fase 2-R1 |
| 2 | Latencia Edge TTS spotter desde región usuario | Medición real | Fase 1b pre-cache |
| 3 | ¿Ducking WASAPI funciona con LMU? | Test pycaw | Fase 1a |
| 4 | `multiprocessing.freeze_support()` en PyInstaller | Test release build | Fase 2-R1 |
| 5 | PTT: ¿stream WS vs capture backend? | Decisión producto | Fase 1b |
| 6 | VRAM LLM vs LMU stutter | Test máquina objetivo | Config LLM |
| 7 | Purga cola obsoleta (SC deploy) | Diseño `PlayCommand.revoke` | Fase 1a |

---

## Puntuación media (ADR original vs ADR-R1)

| Dimensión | ADR-004 original (media 3 rev.) | ADR-R1 (estimado) |
|-----------|--------------------------------|-------------------|
| Fiabilidad | ~4 | **8** |
| Simplicidad | ~3 | **8** |
| Time-to-market | ~5 | **7** |
| Paridad CC | ~6 | **9** |
| Mantenibilidad | ~5 | **7** |
| Testabilidad | ~7 | **8** |
| Operabilidad | ~3 | **8** |

---

## Recomendación final del equipo (post-revisiones)

1. **Adoptar ADR-004-R1** — no tirar el trabajo del ADR; **reorientar Fase 2**.  
2. **Implementar ya:** Fase 0 → Fase 1a → Fase 1b.  
3. **Ship beta** con monolito + audio backend.  
4. **Medir en pista** antes de cualquier split de procesos.  
5. **Actualizar** ADR-004 y checklist (hecho en mismo commit doc).

---

## Próximo paso de implementación

**Fase 0.1:** crear `backend/src/race/tick_loop.py` y eliminar `crewchief_loop.on_frame` de `telemetry_sender_loop` (líneas 167–177 de `websocket.py`).
