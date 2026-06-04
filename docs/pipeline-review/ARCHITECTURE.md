# Pipeline Architecture

**Purpose:** Describe the data flow from Le Mans Ultimate (LMU) through the Windows sidecar, the FastAPI backend, the WebSocket transport, the Zustand store, and the React UI. Each box has a file path, a key class, and a description of what flows in and out. The diagram is the post-review picture; the bugs the review caught are noted in the relevant boxes.

---

## The Pipeline at a Glance

```
┌────────────────────┐     ┌─────────────────────┐     ┌────────────────────────┐
│   LMU (game)       │     │  Windows Sidecar    │     │  FastAPI Backend       │
│   shared memory    │────▶│  StrategyRunner     │────▶│  /ws/sidecar           │
│                    │     │  (sidecar/main.py)  │     │  (websocket.py:204)    │
└────────────────────┘     └─────────────────────┘     └────────┬───────────────┘
         ▲                            ▲                        │
         │ 0.5 Hz                     │ 0.5 Hz                 │ 10 Hz telemetry
         │ (LMUReader                 │ (compute_strategy)     │ (CrewChiefLoop)
         │  reads                     │                        │
         │  shared memory)            │                        ▼
┌────────────────────┐                                          ┌──────────────────────┐
│  LMUReader         │                                          │  FrameCache          │
│  (lmu_reader.py)   │                                          │  (frame_cache.py)    │
│                    │                                          │  ⚠ Bug 2: dedup      │
└────────┬───────────┘                                          │  calls reader once   │
         │                                                      │  too often           │
         │                                                      └──────────┬───────────┘
         │ 10 Hz                                                            │
         └────────────────────────────────────────────────────────────────▶│
                                                                          ▼
                                                              ┌──────────────────────┐
                                                              │  EventEngine         │
                                                              │  (event_engine.py)   │
                                                              │  12 events           │
                                                              └──────────┬───────────┘
                                                                         │ 10 Hz tick
                                                                         ▼
                                                              ┌──────────────────────┐
                                                              │  AudioPlayer         │
                                                              │  (audio_player.py)   │
                                                              │  (real WAV output)   │
                                                              └──────────┬───────────┘
                                                                         │ convert
                                                                         ▼
                                                              ┌──────────────────────┐
                                                              │  event_bridge        │
                                                              │  (event_bridge.py)   │
                                                              │  QueuedMessage →     │
                                                              │  CrewChiefAlertMessage│
                                                              └──────────┬───────────┘
                                                                         │
                                                                         ▼
                                                              ┌──────────────────────┐
                                                              │  manager.broadcast   │
                                                              │  (websocket.py:50)   │
                                                              │  ⚠ Bug 1: receive    │
                                                              │  pattern fragile     │
                                                              └──────────┬───────────┘
                                                                         │ WS
                                                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                       Tauri / React Frontend (port 1420)                              │
│                                                                                       │
│  ┌──────────────────┐    ┌──────────────────┐    ┌────────────────────────────┐     │
│  │  useWebSocket    │    │  useAppStore     │    │  RadioOverlay /            │     │
│  │  (useWebSocket.ts│───▶│  (config.ts)     │───▶│  ConfigTab / App.tsx       │     │
│  │  .ts)            │    │                  │    │  ⚠ Bug 3: no renderer for  │     │
│  │                  │    │                  │    │  crewchief alerts yet      │     │
│  └──────────────────┘    └──────────────────┘    └────────────────────────────┘     │
│                                                                                       │
│  + audioQueue (TTS playback)                                                          │
│  + localStorage("vantare_config") for config persistence                              │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Each Box in Detail

### LMU (the game) — `C:\Program Files (x86)\Steam\steamapps\common\Le Mans Ultimate\`

The Le Mans Ultimate simulation writes telemetry to a Windows shared-memory segment. The C extension `lmu_reader.py` reads from that segment using `ctypes` and `mmap`. The reader is invoked at 10Hz by `CrewChiefRuntime.tick()` (see below) and at 0.5Hz by the sidecar.

The reader's exact protocol is not documented in this repo (it lives in `shared-telemetry/`, which is a separate package). The Python wrapper `LMUReader` exposes `get_flat_dict()` and `get_state()` and the frame_cache/crewchief_loop use those.

**In:** raw LMU shared memory (binary).
**Out:** a flat dict with keys like `session_running_time`, `speed_ms`, `in_pits`, `world_x`, `world_z`, `rivals`, `place`, etc. The shape matches what `FrameCache._merge_rest` and `SpotterService.evaluate_tick` expect.

### Windows Sidecar — `sidecar/src/sidecar/main.py`

A separate process (built via PyInstaller, bundled as `strategy-sidecar` externalBin in the Tauri app). Runs on the same Windows machine as LMU. Reads telemetry from LMU shared memory (independent reader from the backend's), computes strategy advice via `shared-strategy.compute_strategy(frame)`, and pushes the result over WebSocket to the backend at `ws://localhost:8008/ws/sidecar`.

Rate: 0.5Hz (every 2 seconds). The sidecar does its own reading and writing; it does not depend on the backend's `LMUReader`.

**In:** LMU shared memory (binary), backend WebSocket on port 8008.
**Out:** `strategy_frame` JSON to `/ws/sidecar` containing `frame` (the latest telemetry) and `advice` (the `StrategyAdvice` Pydantic model dump).

### Backend `/ws/sidecar` — `backend/src/routers/websocket.py:204-234`

The receiving endpoint. The handler:
1. `await websocket.accept()`.
2. Loop: `data = await websocket.receive_json()`.
3. If `event == "strategy_frame"`, store `app_state.latest_strategy_frame = frame_data`.
4. Index events in `EventStore` (RAG) asynchronously.
5. Handle disconnect gracefully.

The `latest_strategy_frame` is then read by `strategy_sender_loop` (see below) and broadcast to the frontend.

**In:** `strategy_frame` JSON from the sidecar.
**Out:** `app_state.latest_strategy_frame` updated, events indexed in `EventStore`.

### Backend telemetry/strategy sender loops — `backend/src/routers/websocket.py:76-185`

Two concurrent tasks per connected frontend client:

- `telemetry_sender_loop(websocket, app_state)` — runs at 20Hz (50ms interval), sends binary MessagePack telemetry via `websocket.send_bytes(mp_encode(state_dict))`. Prefers the sidecar's `latest_strategy_frame["frame"]` if available, falls back to the local `LMUReader.get_state()`.
- `strategy_sender_loop(websocket, app_state, active_subtasks)` — runs at 0.5Hz (2s interval), sends JSON `{"event": "strategy", "data": advice_dict}` if the advice content changed. Also calls `await _safe_evaluate_cycle(engine, frame, advice)` to run the LLM-driven intelligence layer (excluded from this review).

Both tasks have `asyncio.CancelledError` handling and gracefully terminate on disconnect.

**In:** `app_state.latest_strategy_frame` (from sidecar) or `app_state.telemetry_reader.get_state()` (offline fallback), `app_state.intelligence_engine` (LLM, currently down).
**Out:** binary telemetry frames (20Hz) and JSON strategy events (0.5Hz) to the frontend.

### Backend `/ws` main handler — `backend/src/routers/websocket.py:237-329`

The frontend-facing endpoint. Per connection:
1. `manager.connect(websocket)` — adds to the set of active connections.
2. Start the two sender tasks (telemetry + strategy).
3. Main loop: `await websocket.receive()` for incoming frames (binary telemetry or JSON control).
4. On `WebSocketDisconnect`: cancel all subtasks, wait, disconnect from manager.

**⚠ Bug 1** lives in the main loop's `await websocket.receive()` call (lines 250-285). The pattern is fragile after disconnect. See `BUGS.md` Bug 1 for details.

**In:** binary telemetry frames from frontend (delta-encoded MessagePack), JSON `telemetry` and `pilot_question` events.
**Out:** `app_state.latest_client_frame` updated, `app_state._last_telemetry_t` updated, `evaluate_cycle` and `handle_pilot_question` scheduled on the intelligence engine.

### `LMUReader` — `backend/src/services/lmu_reader.py`

The backend's local copy of the LMU shared-memory reader. Wraps the C extension. Used in offline mode (no sidecar) or as a fallback. The frame_cache and crewchief_loop call it at 10Hz.

**In:** LMU shared memory (binary, cross-process).
**Out:** flat dict via `get_flat_dict()`, or full state via `get_state()`.

### `FrameCache` — `backend/src/services/frame_cache.py:7-66`

Wraps the reader. Has two methods:
- `read_full() -> dict` — returns the latest flat dict, with dedup by `session_running_time`.
- `get_spotter_frame() -> dict` — returns a spotter-specific dict with `rivals`, `session_phase`, `in_pits`, `frame_id`, etc. Always calls `read_full()` first.

Also merges REST data (tire wear, brake wear, damage aero) from `lmu_api.get_garage_wear()` via `_merge_rest`.

**⚠ Bug 2** lives in `read_full()` (lines 15-19). The dedup is half-real: the reader is called on every `read_full()` even when ET is unchanged. See `BUGS.md` Bug 2.

**In:** the wrapped reader, optional `lmu_api.get_garage_wear()`.
**Out:** cached flat dict, or spotter frame dict with `frame_id` incrementing per call.

### `CrewChiefRuntime` — `backend/src/services/crewchief_loop.py:48-230`

The orchestrator. The singleton is created in `init_crewchief(audio_player=...)` from `src/main.py`'s lifespan. `tick()` runs at 10Hz and:

1. `flat = self.cache.read_full()` — get the latest telemetry.
2. Check frame validity (session_running_time > 0, else increment empty counter).
3. Detect session transitions, call `handle_new_session()` if so.
4. Build `GameStateData` via `build(flat, self._prev_gsd)`.
5. Detect state changes via `state_diff.update(flat)`.
6. Populate derived data (`just_gone_green_time`, etc.).
7. Run `NoisyCartesianCoordinateSpotter.trigger(sf, rivals, now)`.
8. `await self.engine.tick_async(self._prev_gsd, gsd)` — run the 12 events.
9. `await loop.run_in_executor(self._executor, self.audio_player.process_queues, ...)` — play queued messages.

**⚠ Bug 4** lives in `__init__` (lines 67-79). The runtime registers the 12 events using `ap=audio_player` but 9 of them only accept `audio_player=`. The construction fails and the runtime falls back to a degraded state. See `BUGS.md` Bug 4.

**In:** `FrameCache`, `StateDiff`, `NoisyCartesianCoordinateSpotter`, `EventEngine`, `AudioPlayer`.
**Out:** updates to `event_flags`, `global_settings`, queued `QueuedMessage` objects, `manager.broadcast` calls (via `event_bridge.queued_to_crewchief_alert`).

### `EventEngine` — `backend/src/intelligence/event_engine.py`

The 12 event classes are registered on the engine at `CrewChiefRuntime.__init__` time. Each event has:
- `applicable(session_type, session_phase) -> bool` — should the event consider this session?
- `should_suppress(gsd) -> bool` — is the event suppressed by global state?
- `on_tick(prev_gsd, curr_gsd) -> List[QueuedMessage]` — produce messages based on telemetry change.

The engine's `tick_async(prev, curr)` iterates over events in sequence order, calls `applicable` and `should_suppress`, and dispatches `trigger_internal(prev, curr)` for those that pass.

**In:** the previous and current `GameStateData`.
**Out:** `QueuedMessage` objects appended to the audio player's queue.

### `AudioPlayer` — `backend/src/services/audio_player.py`

Manages a priority queue of `QueuedMessage` objects. The `process_queues(now, gsd)` method validates each message against the current game state and plays the highest-priority one (TTS or pre-recorded WAV).

In the test environment, the real AudioPlayer is replaced by `RecordingAudioPlayer` (in `test_crewchief_event_flow_e2e.py`) which records `msgs`, `imms`, and `spotter_calls` instead of writing WAV files.

**In:** `QueuedMessage` from events, optional `gsd` for validation.
**Out:** WAV file played (real) or `QueuedMessage` recorded (test).

### `event_bridge.queued_to_crewchief_alert` — `backend/src/services/event_bridge.py:125-146`

Converts `QueuedMessage` to `CrewChiefAlertMessage`. Two responsibilities:

1. **Category inference** (lines 72-78). Maps message name prefixes to categories via a hard-coded prefix map. The map has a bug: `spotter/car_left` does not match the prefix `car_left` because the prefix matcher checks `name.startswith(prefix)`. Falls through to `general`. Documented in `.omo/notepads/pipeline-review/learnings.md` T7 finding #11.

2. **Message formatting** (lines 99-122). Replaces underscores with spaces, applies title case, strips technical suffixes (`" Monitor"`, `" Event"`, `" Reporting"`).

**In:** `QueuedMessage` from the audio player or directly from event_bridge callers.
**Out:** `CrewChiefAlertMessage` for `manager.broadcast`.

### `manager.broadcast` — `backend/src/routers/websocket.py:50-59`

Iterates over `self.active_connections` (a `Set[WebSocket]`) and sends the message to each via `asyncio.gather(..., return_exceptions=True)`. Errors on individual sends are swallowed (return_exceptions=True) so a single client disconnect does not bring down the backend.

**In:** a `BaseMessage` (Pydantic v2 model).
**Out:** JSON `{"event": <event>, "data": <model_dump>}` sent to all active WebSocket clients.

### Frontend `useWebSocket` — `frontend/src/hooks/useWebSocket.ts:11-497`

The React hook that maintains the WS connection. Key responsibilities:

- Connect to `ws://${vllmIP}:${serverPort}/ws` (line 110) with exponential backoff on disconnect (1s → 30s).
- Decode binary MessagePack telemetry (lines 132-187) and update `useAppStore` with `speed`, `rpm`, `gear`, `fuel`, `lap`, `position`, `gaps`, `tyreWear`, `alerts`.
- Parse JSON messages and route to the right store action:
  - `crewchief_alert` (lines 336-358) → `pushCrewchiefAlert(...)`, and for high/critical severity also `setLatestAlert(...)` and `updateTelemetry({alerts: [message]})`.
  - `advice_*` → `addMessageToHistory(...)`, `setLatestAdvice(...)`, `enqueueTts(...)`.
  - `strategy` → `setLatestStrategyAdvice(...)` (via the strategy store action).
  - Spotter alerts (low/medium severity) → `crewchief.latestByCategory[category] = alert` (via `pushCrewchiefAlert`).

**In:** WS messages from the backend (binary + JSON).
**Out:** Zustand store mutations, TTS queue, UI state.

### Frontend `useAppStore` (Zustand) — `frontend/src/store/config.ts`

The single source of truth for the UI. Slices:

- `connectivity` — `wsStatus`, `latency`, `backendHealth`.
- `radio` — `mode`, `currentTokens`, `messageHistory`, `latestAdvice`, `latestAlert`, `micLevel`.
- `telemetry` — `speed`, `rpm`, `gear`, `fuel`, `lap`, `position`, `gaps`, `tyreWear`, `alerts`.
- `crewchief` — `events[]`, `latestByCategory{}`.
- `config` — `vllmIP`, `serverPort`, `micDevice`, `speakerDevice`, `wakeWord`, `sensitivity`, `pttHotkey`, `pttStopHotkey`, `wakeWordEnabled`.

The `config` slice is persisted to `localStorage["vantare_config"]` via `updateConfig(partial)`. The T15 test (`config-persistence.spec.ts`) verifies this round-trip.

**In:** store actions from `useWebSocket`, `usePTT`, `ConfigTab`, etc.
**Out:** reactive UI updates for any component that subscribes to a slice.

### Frontend `RadioOverlay` — `frontend/src/components/RadioOverlay.tsx`

The dashboard view. Renders the radio message history (last 3 messages), telemetry gauges, and the latest advice. Reads from `useAppStore` via a Zustand selector at lines 22-31.

**⚠ Bug 3** lives here (or rather, in the absence of a renderer). The selector does not include `latestAlert`, `crewchief.events`, `crewchief.latestByCategory`, or `telemetry.alerts`. So crewchief alerts flow into the store but are never rendered. See `BUGS.md` Bug 3.

**In:** Zustand store state.
**Out:** rendered React DOM.

### Frontend `ConfigTab` — `frontend/src/components/ConfigTab.tsx`

The settings panel. Renders the `config` slice and exposes `updateConfig(partial)` for user edits. Does NOT read `crewchief` state.

### Frontend `App.tsx`

The root component. Renders the dashboard or the config tab based on `state.screen`. Does NOT read `crewchief` state.

---

## Performance Notes

### FrameCache Dedup (Bug 2)

The dedup logic at `frame_cache.py:15-19` is intended to avoid calling the LMU reader when the elapsed time has not changed. The reader does a cross-process IPC to read LMU shared memory, so saving calls saves real cycles. The current code calls the reader on every `read_full()` and only skips the downstream work. See `BUGS.md` Bug 2 for the fix direction.

### Sidecar Rate (0.5Hz)

The sidecar pushes `strategy_frame` every 2 seconds. The backend's `strategy_sender_loop` reads it at 0.5Hz and only broadcasts to the frontend when the advice content has changed (`advice_dict != last_advice_dict` at `websocket.py:173`). This avoids sending the same advice twice.

### Backend CrewChief Loop (10Hz)

`CrewChiefRuntime.tick()` runs at 10Hz (CREWCHIEF_HZ=10 at `crewchief_loop.py:41`). The telemetry sender loop runs at 20Hz but only sends to the frontend, while the crewchief loop is the one that consumes the frame cache and dispatches events.

### Frontend Reactive Updates

The frontend uses Zustand, which is reactive. Any store mutation triggers a re-render in subscribed components. The T14 test verifies that a `crewchief_alert` push causes the expected store mutations, but the visual re-render is the missing piece (Bug 3).

### WebSocket Backoff

The hook reconnects with exponential backoff starting at 1s and capped at 30s. The T13 test verifies that the hook attempts the connection on boot, fails (no backend), and the store reflects `DISCONNECTED`.

---

## What the LLM Fits In (Current Architecture)

The LLM sits in the backend, between `strategy_sender_loop` and the frontend. When `strategy_sender_loop` runs, it calls `_safe_evaluate_cycle(engine, frame, advice)` which uses the `IntelligenceEngine` to drive an LLM call (via `VLLMClient`). The LLM streams `AdviceStartMessage`, `AdviceTokenMessage`, `AdviceEndMessage` to `manager.broadcast`, which forwards to the frontend. The frontend renders the streaming tokens in the radio overlay.

This whole path is **excluded** from the test review because the LLM server is down. See `LLM-MIGRATION.md` for what changes when the LLM is replaced.

---

## Cross-References

- `BUGS.md` — Bugs 1-5 are mapped to specific boxes in this diagram
- `TEST-INVENTORY.md` — which test file exercises which box
- `LLM-MIGRATION.md` — what changes in the LLM box when the migration lands
- `FIX-PLANS-SUMMARY.md` — the three fix plans that will resolve Bugs 1, 2, 3, 4, and 5
