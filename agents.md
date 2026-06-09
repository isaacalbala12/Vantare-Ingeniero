# AGENTS.md

This file provides guidance to AI agents working in **Vantare-Ingeniero**.

## Project Overview

**Vantare Ingeniero IA** is a real-time race engineer and spotter assistant for **Le Mans Ultimate (LMU)**. It reads live telemetry from LMU shared memory **in-process** on Windows (native telemetry, Task 49 complete), computes deterministic strategy signals, and delivers radio-style guidance via WebSocket + LLM streaming + TTS in a Tauri desktop app.

**Stack:**
- **Backend:** Python 3.12+ / FastAPI (`backend/src`, port 8008)
- **Desktop:** Electron 34 + electron-builder (NSIS) — Hub + overlay + auto-update
- **Frontend:** React 19 + TypeScript + Zustand + TailwindCSS v4 + Vite 6
- **Legacy:** Tauri 2 (`frontend/src-tauri`) — no usar para releases
- **Shared libs:** `shared-telemetry`, `shared-strategy` (no UI deps)

Ver ADR-001: [`docs/decisions/ADR-001-electron-desktop-shell.md`](docs/decisions/ADR-001-electron-desktop-shell.md)

## High-Level Architecture

```
LMU Shared Memory / LMU REST API
        │
        ▼
shared-telemetry (in-process @ 20 Hz via StrategyService)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│                 BACKEND (FastAPI)                   │
│  StrategyService (shared-strategy, deterministic)   │
│  IntelligenceEngine (triggers 0.5Hz + LLM stream)   │
│  SpotterService (20Hz, canned alerts, low latency)  │
│  TTS: Edge / Piper / ElevenLabs / Gemini            │
│  MQTT (opt-in publish)                              │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket :8008
┌──────────────────────▼──────────────────────────────┐
│              ELECTRON (Hub + Overlay)               │
│  useWebSocket → priorityAudioQueue (IMMEDIATE/NORMAL)│
│  PTT → LLM, Speech Recognition, spotter phrases     │
│  ConfigTab / Hub sections, tray, electron-updater   │
└─────────────────────────────────────────────────────┘
```

**Paridad Crew Chief:** [`docs/architecture/pipelines/README.md`](docs/architecture/pipelines/README.md) · [`docs/architecture/cc-portable-logic-analysis.md`](docs/architecture/cc-portable-logic-analysis.md)

## Repository Layout

| Directory | Purpose |
|-----------|---------|
| `backend/` | FastAPI server, intelligence, triggers, spotter, transport, persistence, services |
| `frontend/` | UI, hooks, WebSocket/audio pipeline, Vitest tests, config UI |
| `shared-strategy/` | Deterministic fuel/tyre/brake/hybrid/pit/competitor calculations |
| `shared-telemetry/` | LMU shared-memory reader and telemetry models |
| `.omo/` | Plans, evidence, checklists (parity drafts, LMU validation) |
| `scripts/` | Verification gates (`verify_audio_pipeline.py`, `verify_spotter_pipeline.py`) |
| `docs/` | Project docs (see stale-doc warning below) |

### `backend/` (key modules)

- `src/main.py` — FastAPI app, lifespan, service init
- `src/intelligence/engine.py` — `IntelligenceEngine`: triggers, LLM streaming, preemption, pearls, competitor monitor
- `src/intelligence/triggers.py` — 18+ race-condition triggers (`get_all_triggers()`)
- `src/intelligence/spotter.py` — 20Hz spotter (cartesian + path + world-space)
- `src/intelligence/spotter_geometry.py`, `spotter_state.py`, `cartesian_spotter.py` — spotter stack
- `src/intelligence/competitor_queries.py` — rival gap/lap queries (PTT/tools)
- `src/intelligence/pearls_of_wisdom.py` — comeback/standard pearls (partial wiring)
- `src/intelligence/corner_names.py`, `track_spline.py` — track landmarks (5 circuits)
- `src/intelligence/flags_monitor.py` — SC/FCY/yellow/blue/red
- `src/intelligence/driver_names.py`, `time_format.py` — fuzzy names, colloquial time
- `src/services/mqtt_service.py` — MQTT publish (implemented, needs E2E validation)
- `src/services/tts_service.py`, `edge_tts_service.py`, etc. — multi-backend TTS
- `src/persistence/history_store.py`, `profile_store.py`, `event_store.py` — fuel history, profiles, RAG
- `src/models/messages.py` — Pydantic WS models
- `src/config.py` — settings from `backend/.env`

### `frontend/` (key modules)

- `src/hooks/useWebSocket.ts` — WS client, TTS enqueue, advice streaming
- `src/hooks/usePTT.ts`, `useHotkey.ts` — push-to-talk (default `Ctrl+Shift+Space`, not bare `P`)
- `src/services/priorityAudioQueue.ts` — **dual-priority playback** (IMMEDIATE vs NORMAL)
- `src/services/alertVoice.ts` — voice category rules (`pearl` currently no-voice)
- `src/services/spotterPhrases.ts`, `spotterCommands.ts` — spotter canned phrases + fast-path commands
- `src/services/ttsCache.ts` — TTS cache with voice hash
- `src/store/config.ts`, `src/components/ConfigTab.tsx` — user config and profiles
- `src-tauri/src/audio_duck.rs` — LMU audio ducking

## Audio Pipeline (Current)

### Dual-priority queue

Frontend uses **two playback priorities** in `priorityAudioQueue.ts`:

| Priority | Source | Behavior |
|----------|--------|----------|
| `IMMEDIATE` | Spotter alerts, critical strategy alerts | Preempts NORMAL playback |
| `NORMAL` | LLM advice (`advice_end`), commentary | Queued sequentially |

- `enqueueImmediate()` interrupts currently playing NORMAL audio.
- `stopNormal()` clears normal queue; immediate behavior preserved.
- Ducking: `duck_lmu` invoke during playback (`audio_duck.rs`).

### WebSocket → TTS flow

`useWebSocket.ts` handles:
- `alert` — spotter/strategy/system (often → IMMEDIATE via `classifyTtsPriority`)
- `advice_start` / `advice_token` / `advice_end` — LLM streaming → NORMAL queue on `advice_end`

Anti-spam: spoken dedupe cooldown (`TTS_SPOKEN_COOLDOWN_MS`), queue cap (`TTS_QUEUE_MAX`).

### Categories

- Spotter: `category` on alert messages, canned backend text + frontend phrase mapping
- Pearls: `category="pearl"` from `engine.py` — in `NO_VOICE_CATEGORIES` today (planned audible in A2)
- Commentary: `commentary_end` from CommentaryOrchestrator (batch/debounce, A0 foundation)

## Intelligence Layer

### Implemented

- **Triggers** (`triggers.py`): FuelCritical, FlagsMonitor, MulticlassWarning, DriverSwap, PenaltyMonitor, PushNow, SessionEnd, BrakeWear, TyreDeg, Hybrid, Weather, PitWindow, CompetitorPitted, GapClosed, PhaseChanged, PilotQuestion, etc.
- **Spotter** (`spotter.py`): triple detector, state machine, multiclase geometry (`driver_class` in hits), cooldowns
- **LLM path**: `llm_pending` → streaming tokens → `advice_end`; priority preemption (`cancel_current_llm`)
- **Competitor tools**: `apply_monitor_competitor` in `engine.py` + `competitor_queries.py` (PTT, not proactive yet)
- **Pearls**: FAST_LAP/OVERTAKE wired; COMEBACK/STANDARD exist but incomplete

### A0 foundation (implemented)

- **`PersonalityPack`** — `backend/src/intelligence/personality_pack.py`
- **`VerbosityController`** — `backend/src/intelligence/verbosity_controller.py`
- **`CommentaryOrchestrator`** + **`EventRegistry`** — `commentary_end` WS event
- LLM tool **`set_verbosity`** via PTT
- Frontend dual TTS voice + ConfigTab personality/verbosity UI

### Planned (A1+)

- Wire race monitors to `enqueue_commentary()` (A3+)
- LLM batch inside CommentaryOrchestrator (A0 uses deterministic text join)
- Sync frontend verbosity/personality to backend over WS

## Baseline Inventory (Already Exists — Do Not Reimplement)

Validated in `.omo/drafts/comparacion-crewchief.md` and source:

- Spotter stack (geometry, state, cartesian, multiclase detection)
- 18+ triggers + flags/penalties/multiclase ALERT_ONLY
- `competitor_queries.py` + monitor tool in engine
- `driver_names.py` (fuzzy; no CC 5000 WAV approach — use TTS)
- `corner_names.py` + `track_spline.py` (Spa, Monza, Le Mans, Silverstone, Portimão)
- `shared-strategy/` fuel, tyres, hybrid, pit_window, `fuel_needed_to_finish`
- Blue flag, DRS, invalid lap, penalties, session_over in telemetry/strategy
- **`mqtt_service.py`** complete — A8 is validate/wire, not build
- **Audio ducking** (`audio_duck.rs`)
- **Profile store** + ConfigTab UI
- **Fuel history** (`history_store.py`)
- **Dual priority audio** (`priorityAudioQueue.ts`)
- **Multi-backend TTS** (Edge default alpha)

## CrewChief Parity — User Decisions (Authoritative)

Source: `.cursor/plans/paridad_crew_chief_22a9ebbf.plan.md`

| Topic | Decision |
|-------|----------|
| Driver queries | **PTT → LLM only** (no CC grammar/SRE) |
| Proactive comments | **LLM batch** + aggressive TTS cache |
| Pit management | **Read-only verbal** in alpha (no LMU REST write) |
| Overlays / VR | **Beta** — out of alpha |
| Personalities | **Engineer profile** + **spotter profile** (prompts + distinct TTS voices) |
| Action commands | LLM tools via PTT; keep fast-path spotter on/off (`spotterCommands.ts`) |
| TTS | Edge alpha → Gemini beta |
| Language | **Spanish only** (alpha/beta) |
| Verbosity | Silent / Normal / Detailed + braking-zone mute when telemetry reliable |

**Explicitly excluded from alpha:** grammar command engine, pit write API, in-game overlays.

## Implementation Phases (A0–A8 + Beta)

Plan: `C:\Users\isaac\.cursor\plans\paridad_crew_chief_22a9ebbf.plan.md`

| Phase | Scope |
|-------|-------|
| **A0** | PersonalityPack, CommentaryOrchestrator, `commentary_end` WS, dual TTS voice, VerbosityController + LLM tools |
| **A1** | Extend existing spotter — multiclase narration, hold/closing speed, params UI, profile phrases (not rewrite detector) |
| **A2** | Pearls COMEBACK/STANDARD audible, remove pearl from no-voice, verbosity limits |
| **A3** | LapTime/Position/Gap/SessionEnd/PushNow monitors; race start "Go go go"; **track landmarks in narration** |
| **A4** | Tyre/Fuel/Engine/Brake/Damage/DRS monitors; **FuelPercentileCalculator** (history_store) |
| **A5** | Full flags, FrozenOrder, penalties, multiclass proactive, driver swaps |
| **A6** | WatchedOpponents proactive + TTS names (extend existing competitor_queries) |
| **A7** | Attack/defend, expand corner DB, pit readonly + **pit-exit position prediction** |
| **A8** | Volume boost, profile polish, **MQTT E2E validation**, LMU checklist, doc sync (~1 week) |
| **Beta** | Gemini TTS premium, overlays, pit LMU write, English |

**Recommended order:** A0 → A1+A2 → A3 → (A4/A5/A6 parallel) → A7 → A8.

Draft-driven adjustments (in plan): landmarks moved to A3; A8 MQTT shortened; A1 scope reduced.

## Testing and CI

### Automated gate

```powershell
python scripts/verify_audio_pipeline.py
```

Runs backend pytest matrix + frontend vitest matrix (67 pytest + 54 vitest as of last gate).

Key test files:
- `backend/tests/test_audio_trigger_matrix.py`
- `backend/tests/test_spotter_audio_contract.py`
- `backend/tests/test_preemption.py`
- `frontend/src/__tests__/audioTriggerMatrix.test.ts`
- `frontend/src/__tests__/audioPipeline.integration.test.ts`
- `frontend/src/__tests__/fixtures/audioTriggerMatrix.ts`

### Spotter pipeline

```powershell
cd backend
python -m pytest tests/test_spotter*.py tests/test_cartesian_spotter.py tests/test_spotter_state.py tests/test_spotter_e2e.py -v
python ../scripts/verify_spotter_pipeline.py
python ../scripts/verify_audio_pipeline.py

cd ../frontend
npm test -- audioTriggerMatrix.test.ts audioPipeline.integration.test.ts alertVoice.test.ts priorityAudioQueue.test.ts ttsCache.test.ts useWebSocket.spotter.test.ts spotterPipeline.integration.test.ts --run
```

### LMU manual checklists

- Audio: `.omo/evidence/audio-lmu-validation.md`
- Spotter: `.omo/evidence/spotter-lmu-validation.md`

Run these after local CI gates pass, before claiming LMU parity.

## Common Commands

### Backend (Windows native — default after Task 49-S7)

```powershell
cd backend
$env:VANTARE_NATIVE_TELEMETRY='1'
python run_dev.py --no-reload
```

Or from repo root: `.\scripts\dev.ps1`

### Backend (generic uvicorn)

```bash
cd backend && pip install -e . && uvicorn src.main:app --reload --host 127.0.0.1 --port 8008
```

### Frontend

```bash
cd frontend
npm install
npm run dev           # Vite (5173)
npm run tauri dev     # Tauri dev
npm run tauri build   # Production build
```

### Shared libraries

```bash
pip install -e shared-telemetry/ -e shared-strategy/ -e backend/
cd shared-strategy && pip install -e ".[dev]" && pytest
```

### Environment

Create `backend/.env`:

```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-vllm-endpoint/v1
LLM_MODEL=your-model
```

## Doc Freshness Warning

`docs/crewchief-comparison.md` is **potentially stale** — it marks several features as missing that now exist (spotter, ducking, MQTT, competitor queries, etc.).

**Source of truth priority:**
1. Current source code
2. `.omo/drafts/comparacion-crewchief.md`
3. `.cursor/plans/paridad_crew_chief_22a9ebbf.plan.md`
4. `docs/crewchief-comparison.md` (update in A8)

## Agent Conventions

- **Minimal scope** — align work to current phase (A0–A8); avoid broad rewrites.
- **Extend, don't duplicate** — spotter core, MQTT, dual-priority queue, triggers already exist.
- **Match existing patterns** — naming, types, WS contracts, test fixtures before adding abstractions.
- **Preserve WS compatibility** unless migrating backend + frontend together.
- **Code over docs** — when docs conflict with code, trust code and flag drift.
- **No commits** unless the user explicitly asks.
- **Spanish-first** copy for user-facing strings in alpha/beta.

## Key File Paths

| Area | Path |
|------|------|
| Parity draft | `.omo/drafts/comparacion-crewchief.md` |
| **Complete port plan (Tasks 0–48)** | `docs/superpowers/plans/2026-06-07-crewchief-complete-port.md` |
| **Decisions + 14-day sprint** | `docs/superpowers/plans/2026-06-07-crewchief-decisions.md` |
| **Pipeline test template (L1–L5)** | `docs/superpowers/plans/2026-06-07-crewchief-pipeline-test-template.md` |
| Foundation TDD (Tasks 1–14) | `docs/superpowers/plans/2026-06-07-crewchief-parity-port.md` |
| Comparison doc (stale-risk) | `docs/crewchief-comparison.md` |
| Intelligence engine | `backend/src/intelligence/engine.py` |
| Triggers | `backend/src/intelligence/triggers.py` |
| Spotter | `backend/src/intelligence/spotter.py` |
| Competitor queries | `backend/src/intelligence/competitor_queries.py` |
| MQTT | `backend/src/services/mqtt_service.py` |
| WebSocket hook | `frontend/src/hooks/useWebSocket.ts` |
| Priority audio queue | `frontend/src/services/priorityAudioQueue.ts` |
| Config | `frontend/src/store/config.ts`, `frontend/src/components/ConfigTab.tsx` |
| Audio gate | `scripts/verify_audio_pipeline.py` |
| LMU audio checklist | `.omo/evidence/audio-lmu-validation.md` |
| LMU spotter checklist | `.omo/evidence/spotter-lmu-validation.md` |
