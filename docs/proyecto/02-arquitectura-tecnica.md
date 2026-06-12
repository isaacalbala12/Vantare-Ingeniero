# 02 — Arquitectura técnica

## Diagrama runtime (estado v0.5 — Voice Beta + Electron)

```
┌─────────────────────────────────────────────────────────────────┐
│  Le Mans Ultimate                                                │
│  Shared memory (pyLMUSharedMemory) + REST API :6397 (pit menu)   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  backend.exe (PyInstaller, FastAPI + asyncio)                    │
│                                                                  │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │ TelemetryReader │  │ race_loop @20Hz  │  │ voice_loop      │ │
│  │ shared-telemetry│→ │ StrategyService  │→ │ pygame + cola   │ │
│  └─────────────────┘  │ spotter global   │  │ TTSManager      │ │
│                       │ crewchief_events │  │ moderador       │ │
│                       └────────┬─────────┘  └────────▲────────┘ │
│                                │                      │         │
│  ┌─────────────────────────────▼──────────────────────┴───────┐ │
│  │ IntelligenceEngine (triggers 0.5Hz, PTT, proactive)        │ │
│  │ LLM client (streaming) · PersonalityPack · PhrasePicker     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  HTTP :8008  — /health, /tts, /phrases, /transcribe             │
│  WebSocket   — telemetría, alertas, config_update, playback    │
└────────────────────────────┬────────────────────────────────────┘
                             │ ws://127.0.0.1:8008/ws
┌────────────────────────────▼────────────────────────────────────┐
│  Electron (frontend)                                               │
│  · Hub React — configuración, perfiles, frases, actualizaciones   │
│  · Overlay — indicador radio (speaking/listening), no telemetría  │
│  · Auto-update — electron-updater → GitHub Releases               │
└───────────────────────────────────────────────────────────────────┘
```

**Invariantes Voice Beta (ADR-004-R1):**

- Un **snapshot/tick** global por frame de carrera
- **Un evaluador** spotter + CC (no por cliente WebSocket)
- **Audio solo backend** — frontend no reproduce TTS principal
- **Un `backend.exe`** por sesión de juego

Registro completo: [`../architecture/2026-06-07-rearchitecture-decisions-record.md`](../architecture/2026-06-07-rearchitecture-decisions-record.md).

---

## Stack tecnológico

| Capa | Tecnología | Notas |
|------|------------|-------|
| Backend API | Python 3.12, FastAPI, uvicorn | Async, lifespan init |
| Telemetría | `shared-telemetry` (Python) | LMU mmap; no editar hasta 1.1 |
| Estrategia | `shared-strategy` | Fuel, tyres, pit window determinista |
| Inteligencia | Módulos propios + `crewchief_events/` | ~25 módulos CC portados |
| LLM | httpx → API OpenAI-compatible | StepFun, etc. vía `.env` |
| TTS | Edge (default), Gemini (opcional), Piper, ElevenLabs | Routing por rol engineer/spotter |
| Audio | pygame en `voice_loop` | Cola prioridad, ducking opcional |
| Frontend | React 19, TypeScript, Zustand, Tailwind v4 | Vite build |
| Desktop shell | **Electron** (migrado desde Tauri) | NSIS installer |
| Empaquetado | PyInstaller + electron-builder | `scripts/build-desktop.ps1` |
| CI | GitHub Actions | `ci.yml`, `release-desktop.yml` on tag |

---

## Shell desktop: Electron vs Tauri

El repo **migró a Electron** para instalador, auto-update y estabilidad del shell. Tauri/Rust queda como legado en `frontend/src-tauri/` (binaries backend empaquetados, iconos).

Análisis: [`../arquitectura-shell-desktop.md`](../arquitectura-shell-desktop.md).

ADRs:

- [`../decisions/ADR-001-electron-desktop-shell.md`](../decisions/ADR-001-electron-desktop-shell.md)
- [`../decisions/ADR-002-github-releases-auto-update.md`](../decisions/ADR-002-github-releases-auto-update.md)
- [`../decisions/ADR-003-native-telemetry-windows.md`](../decisions/ADR-003-native-telemetry-windows.md)
- [`../decisions/ADR-004-dual-process-voice-architecture.md`](../decisions/ADR-004-dual-process-voice-architecture.md)

---

## Flujo de datos por frame (~20 Hz)

1. `TelemetryReader` lee mmap LMU
2. `StrategyService.snapshot_frame()` normaliza frame
3. **Spotter** evalúa proximidad cartesiana → mensajes spotter
4. **CrewChiefEventSuite** evalúa módulos (fuel, flags, lap times, pearls, …)
5. Mensajes entran a **VoiceService** / cola con prioridad
6. **WebSocket** emite telemetría + eventos al frontend
7. **Overlay** muestra estado playback vía `voice_playback_start/end`

El **IntelligenceEngine** (triggers LLM @ 0.5 Hz) y **PTT** corren en paralelo con reglas de preemption documentadas en `engine.py`.

---

## Configuración Hub ↔ Backend

Config persistida en frontend (`localStorage` + Zustand) y sincronizada vía WebSocket `config_update` / `config_ack`.

Campos relevantes v0.5:

| Campo | Efecto |
|-------|--------|
| `personalityProfileId` | formal / standard / aggressive |
| `swearyMessages` | tono coloquial ingeniero |
| `proactivityLevel` | low / normal / high — filtra emisiones proactivas |
| `pearlFrequency` | 0–1 — frecuencia perlas de sabiduría |
| `ttsProviderEngineer` / `ttsProviderSpotter` | edge / gemini |
| `engineerEnabled` / `spotterEnabled` | toggles servicio |
| `speakOnlyWhenSpokenTo` | silencia ingeniero proactivo, no spotter |

Invariante **I1**: nuevos campos config deben aparecer en payload WS y `config_ack`.

---

## Persistencia fuera del repo

| Ruta | Contenido |
|------|-----------|
| `%APPDATA%/Vantare/phrases/user_phrases.json` | Overrides frases usuario (v0.4) |
| `%APPDATA%/Vantare/` (otros) | Historial, perfiles QA, traces debug |
| `backend/.env` | API keys (nunca commitear) |

---

## Pipelines documentados (CrewChief parity)

Serie en [`../architecture/pipelines/`](../architecture/pipelines/):

| # | Pipeline |
|---|----------|
| 00 | Charter paridad + referencia CC |
| 01 | Game state ingest |
| 02 | Spotter channel |
| 03 | Engineer events channel |
| 04 | Playback moderator |
| 05 | Pilot commands (PTT) |
| 06 | Deltas implementación Vantare |

---

## Era futura 1.1 (referencia, no implementar aún)

```
LMU / iRacing → shared-telemetry (Rust, un crate)
                    ├── Vantare backend.exe (voz + CC)
                    └── Go overlay (HUD, standalone)
Suite launcher opcional + bus MQTT/WS entre peers
```

Detalle: [`../ROADMAP-1.0.md`](../ROADMAP-1.0.md) §4.3.
