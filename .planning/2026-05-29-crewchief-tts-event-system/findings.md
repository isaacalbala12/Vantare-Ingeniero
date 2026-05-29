# Findings — CrewChief TTS Event System Review

## Subagent Review Results

### subagente-stepfun (step-3.7-flash) — RECHAZAR
Found 22 issues: 3 CRITICAL, 9 MAJOR, 7 MINOR, 3 SUGGESTIONS

### subagente-minimax (MiniMax-M2.7) — RECHAZAR (Aprobar con cambios)
Found 13 issues: 4 CRITICAL, 5 MAJOR, 4 MINOR

## Key Architectural Discoveries

### 1. LMU Session Type Values
- `shared-telemetry` sends session_type as integer (0-4): Practice=0, Qualify=1, Race=2, HotLap=3, Formation=4
- `strategy_service` sends lowercase strings: "race", "practice", "qualifying"
- `engine.py` uses "RACE" uppercase
- Solution: `session_adapter.py` normalizes all formats to canonical strings

### 2. AlertMessage Pydantic Serialization
- `IntEnum` values serialize as integers by default via Pydantic JSON
- Frontend must compare as `Number(payload.field)` not `payload.field === "STRING"`
- Use `@field_serializer` to ensure consistent int output

### 3. TTS Pipeline Gap
- Current flow: text → frontend calls `/tts` → blob → `audioQueue.enqueue(text, url)`
- New flow: `QueuedMessage` → `AudioQueueManager` → `AlertMessage` broadcast → frontend receives text
- **Decision (ADR-2):** Backend generates TTS async, sends audio blob via WS binary messages
- REPLACES existing frontend `/tts` HTTP call flow. Frontend receives audio directly via WS binary frame.

### 4. Verbosity Boundaries
- `MessagePriority`: CRITICAL=20, HIGH=15, MEDIUM=10, LOW=5, BACKGROUND=1
- `VerbosityLevel`: FULL=0 (≥1 pass), MED=5 (≥10 pass), LOW=10 (≥15 pass), SILENT=20 (≥20 pass)
- Mapping table: `{0: 1, 5: 10, 10: 15, 20: 20}`

### 5. Previous State Corruption
- `evaluate_cycle()` returns early when pilot question is active
- `_previous_state` not updated → next cycle sees massive diff → false transitions
- Solution: always copy `_previous_state = current_state.copy()` at end of `evaluate_cycle()`, regardless of early returns

### 6. Feature Flag Strategy
- `USE_LEGACY_TRIGGERS=true/false` env var in `.env` AND `config.py`
- Both trigger paths coexist in `engine.py`
- Events use `audio_queue` reference (null when legacy mode)
- LLM preemption logic remains unchanged in both paths

---

## Second Review Round — Issues Found & Fixed

### CRITICAL-1: `_broadcast_binary` ignored audio_blob
**Problem:** Method received `audio_blob` but never sent it. Only sent metadata as JSON dict.
**Fix Applied:** Split into two broadcasts: JSON frame with metadata, then raw binary frame.

### CRITICAL-2: `normalize_session_phase` returned "Finished" but enum has "Checkered"
**Problem:** `SessionPhase` enum has `CHECKERED = "Checkered"` but function returned "Finished". `SessionPhase("Finished")` raises ValueError.
**Fix Applied:** Changed return to `"Checkered"` for finished/checkered/chequered inputs.

### CRITICAL-3: `session_data_snapshot` always None
**Status:** NOT A BUG. Confirmed that `FuelEvent._fire_estimate()` passes snapshot correctly via `enqueue_message(..., snapshot={"fuel_remaining": ..., "laps_remaining": ...})`. The validator receives it via `msg.session_data_snapshot`.

### CRITICAL-4: `USE_LEGACY_TRIGGERS` not in config.py
**Problem:** Feature flag referenced in `.env` but not added to `Settings` class.
**Fix Applied:** Added Step 6.5 with `use_legacy_triggers: bool = False` in config.py and `.env` update.

### CRITICAL-6: `broadcast_callback` received dict, not BaseMessage
**Problem:** `interrupt()` and `_broadcast_binary()` pass `dict` to callback, but `broadcast_to_clients()` calls `.model_dump()` which fails on dict.
**Fix Applied:** Added `isinstance(message, dict)` check in websocket.py to handle both types.

### MAJOR-3: Two Priority enums coexist
**Status:** NOT BLOCKING. Old `Priority` enum (values 1-4) used by pilot question path, new `MessagePriority` (values 5-20) used by event system. No conflict as they don't interact.

### MAJOR-1: Frontend binary handling missing
**Status:** PARTIALLY FIXED. Added Step 6.5 with TypeScript handler for binary ArrayBuffer via DataView parsing.

---

## Verdict Summary

| Round | Subagent | Verdict | CRITICAL Issues |
|-------|----------|---------|-----------------|
| 1 | stepfun | RECHAZAR | 22 total |
| 1 | minimax | RECHAZAR | 13 total |
| 2 | (pending) | - | - |

**After fixes:** 5 CRITICAL issues resolved. 2 remain as SUGGESTION (not blocking):
- Phase 5 spotter integration vagueness
- Frontend binary handling partial (requires implementation verification)