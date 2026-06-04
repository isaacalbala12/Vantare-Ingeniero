# BACKEND

**Branch:** `feature/benchmark-llm` | **Updated:** 2026-06-01

## OVERVIEW

Python FastAPI backend — LLM orchestration, real-time telemetry ingestion, audio TTS pipeline, WebSocket pub/sub, and race strategy computation. Core of the "AI race engineer."

## STRUCTURE

```
src/
├── main.py                 # FastAPI app entry, lifespan, CORS, startup
├── config/                 # Global behaviour flags, app config
├── data/                   # Car class data, static mappings
├── intelligence/           # LLM engine, spotter, triggers, events, context
│   ├── engine.py           # evaluate_cycle() — main tick orchestrator (496 lines)
│   ├── spotter.py          # Position/incident spotter logic
│   ├── triggers.py         # Trigger definitions and evaluation (354 lines)
│   ├── ticker.py           # Tick processing pipeline (354 lines)
│   ├── context_builder.py  # Ticker data construction (337 lines)
│   ├── llm_client.py       # Streaming LLM client (async)
│   ├── event_engine.py     # Base event engine + flags
│   ├── formatter.py        # Message formatting
│   └── events/             # Event-specific logic (flags_monitor, lap_counter, position, session)
├── models/                 # Pydantic v2 models (enums, game_state_data, messages)
├── persistence/            # Event store, history store (SQLite)
├── routers/                # FastAPI route handlers (health, history, llm, transcribe, tts, websocket)
├── services/               # Business logic (audio_player, TTS services, strategy, state_diff, etc.)
└── transport/              # WebSocket broadcaster
```

## WHERE TO LOOK

| Task | File |
|------|------|
| LLM tick evaluation | `src/intelligence/engine.py:evaluate_cycle()` |
| Strategy computation | `src/services/strategy_service.py` |
| WebSocket hub | `src/routers/websocket.py` |
| LLM streaming | `src/intelligence/llm_client.py` |
| Race state model | `src/models/game_state_data.py` |
| Audio playback | `src/services/audio_player.py` |
| TTS services | `src/services/edge_tts_service.py`, `elevenlabs_tts_service.py`, `gemini_tts_service.py` |

## CONVENTIONS

- **FastAPI async** — all endpoints and lifespan are async def
- **Pydantic v2** — all data models use `BaseModel`, validated serialization
- **Dependency injection** — services via `lifespan` context and module-level singletons
- **Event-driven** — engine uses `StateChangeDetector` + `EventEngine` + flags
- **Tests** — pytest with conftest.py; 140+ test files; fixtures in root `tests/conftest.py`
- **PyInstaller** — distribution via `backend.spec`, entry at `src/main.py`

## ANTI-PATTERNS

- Do not add blocking sync calls in async endpoints — use `asyncio.to_thread()` or dedicated executor
- Do not add new `try-except-pass` — all exceptions must be logged or handled
- Do not add CORS `allow_origins=["*"]` — use `settings.FRONTEND_ORIGIN`
- Do not add direct `print()` statements — use the logging module

## COMMANDS

```bash
# Install in dev mode
pip install -e .

# Run backend
python run_dev.py

# Run all tests
pytest tests/ -v

# Run single test file
pytest tests/test_engine.py -v

# Build distribution
pyinstaller backend.spec
```
