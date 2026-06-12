# AGENTS.md
This file provides guidance to various AI agents when working with code in this repository.

## Project Overview

**Vantare Ingeniero IA** is a real-time race strategy assistant for Le Mans Ultimate (LMU). It reads live telemetry from shared memory, computes pit strategies deterministically, and provides natural-language advice to the driver via an LLM backend and TTS synthesis. The frontend is an **Electron/React/TypeScript** desktop app (Hub + overlay); audio playback runs in the **Python backend** (Voice Beta v0.2.14+).

> **Canonical documentation:** [`docs/proyecto/README.md`](docs/proyecto/README.md) — handbook, architecture, roadmap, orchestrator prompt.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                  FRONTEND (Tauri)                   │
│  React + TypeScript + Zustand + WebSocket client    │
│  PTT capture, Speech Recognition, TTS playback      │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket :8008
┌──────────────────────▼──────────────────────────────┐
│                 BACKEND (FastAPI)                   │
│  ┌─────────────────┐  ┌────────────────────────┐    │
│  │ TelemetryReader │  │ IntelligenceEngine     │    │
│  │ (shared-telemetry)│ │ (LLM triggers, 0.5Hz) │    │
│  └────────┬────────┘  └──────────┬─────────────┘    │
│           │                      │                  │
│           │              ┌───────▼────────┐         │
│  ┌────────▼────────┐     │ LLM Client     │         │
│  │ StrategyService │     │ (vLLM stream)  │         │
│  │ (shared-strategy)│    └────────────────┘         │
│  └────────┬────────┘                                 │
│           │                                          │
│  ┌────────▼────────┐                                 │
│  │ TTS Services    │  Edge TTS (cloud, default)      │
│  │                  │  Piper ONNX (local)             │
│  │                  │  ElevenLabs (cloud)            │
│  └─────────────────┘                                 │
└─────────────────────────────────────────────────────┘
       ▲                              ▲
       │        Shared libs           │
┌──────▼──────────────────────────────▼───────┐
│         SHARED LIBRARIES (no UI deps)       │
│  shared-telemetry/  →  LMU shared memory    │
│  shared-strategy/   →  Strategy calculations │
└─────────────────────────────────────────────┘
```

## Core Directories

### `backend/`
- FastAPI async backend (`src/main.py`). Initializes all services in lifespan handler.
- `src/intelligence/engine.py`: IntelligenceEngine — orchestrates triggers at 0.5Hz, manages LLM streaming, preemption.
- `src/intelligence/triggers.py`: 12 race-condition triggers (FuelCritical, SafetyCar, BrakeWear, TyreDeg, Hybrid, Weather, PitWindow, etc.).
- `src/intelligence/llm_client.py`: VLLM streaming client using httpx.
- `src/routers/websocket.py`: WebSocket endpoint — sends telemetry at 20Hz, strategy at 0.5Hz. Evaluates intelligence engine per cycle.
- `src/services/`: EdgeTTS, Piper TTS, ElevenLabs TTS, Gemini TTS, LMU API poller, StrategyService, LLM service.
- `src/persistence/history_store.py`: Fuel consumption per-lap JSON persistence.
- `src/models/messages.py`: Pydantic message models (BaseMessage, LLMPendingMessage, AlertMessage, AdviceEndMessage, etc.).
- Configuration via `src/config.py` — reads `backend/.env`.

### `frontend/`
- Tauri 2 + React 19 + TypeScript + Zustand + TailwindCSS v4.
- `src/App.tsx`: Main component — PTT orchestration, Speech Recognition, TTS queue.
- `src/store/appStore.ts`: Zustand store for radio mode, telemetry, alerts, config.
- `src/hooks/`: `useWebSocket`, `usePTT`, `useAudioCapture`, `useAudioContext`, `useHotkey`.
- `src/services/audioQueue.ts`: Sequential TTS playback queue.
- `src/services/api.ts`: HTTP calls to backend health/tts endpoints.
- `src/__tests__/`: Vitest unit tests for filters, configStore, audioQueue.

### `frontend/src-tauri/`
- Rust/Tauri app — system tray, global shortcuts, window management.
- `src/main.rs`: Tauri entry point. `src/lib.rs`: placeholder lib.

### `shared-telemetry/`
- Python library reading LMU shared memory (`pyLMUSharedMemory/`). No UI deps.
- `TelemetryReader` class: daemon thread, configurable frequency, offline/simulated mode.
- Pydantic models: `RaceState`, `SessionData`, `VehicleData`, `TyreData`, `BrakeData`, `EngineData`, `DriverInputs`, `LapData`.

### `shared-strategy/`
- Deterministic race strategy: fuel consumption, tyre wear, pit window calculation, stint planning.
- Pydantic models: `TelemetryFrame`, `FuelState`, `TyreState`, `BrakeState`, `HybridState`, `StintData`, `CompetitorTrackerState`.
- Modules: `fuel.py`, `tyres.py`, `brakes.py`, `hybrid.py`, `pit_window.py`, `competitors.py`, `calculation.py`.

## Common Commands

### Backend
```bash
# Development
cd backend && pip install -e . && uvicorn src.main:app --reload --host 127.0.0.1 --port 8008

# Production (PyInstaller)
# Build: backend/scripts/build.sh
# Run: backend/dist/backend/backend.exe
```

### Frontend
```bash
cd frontend
npm install
npm run dev           # Vite dev server (port 5173)
npm run build          # TypeScript + Vite production build
npm run tauri dev      # Tauri dev (requires Rust)
npm run tauri build   # Tauri production build
```

### Shared Libraries
```bash
# Install both shared libs in dev mode
pip install -e shared-telemetry/ -e shared-strategy/ -e backend/

# Run tests
cd shared-strategy && pip install -e ".[dev]" && pytest

# Smoke test
python backend/qa_test_script.py
```

### Environment
Create `backend/.env` with:
```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-vllm-endpoint/v1
LLM_MODEL=your-model
```