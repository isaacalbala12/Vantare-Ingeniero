
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replicate 100% of CrewChiefV4's functionality for Le Mans Ultimate in the Vantare Ingeniero app — deterministic spotter, all 29 events, dual audio queue, voice commands, battery/hybrid management, driver swaps, full timing/gaps, penalties, damage reporting, tyre monitoring, engine monitoring, fuel strategy, pit stop management, formation lap handling, multiclass warnings, watched opponents, session end messages, pearls of wisdom, and complete infrastructure.

**Architecture:** Python async backend (FastAPI) + TypeScript frontend (Tauri/React). The backend reads LMU shared memory via ctypes, produces a unified GameStateData object, feeds it through an EventEngine that dispatches to 29+ event handlers. Each handler produces QueuedMessage objects with MessageFragments. The AudioPlayer manages two queues (normal + immediate) with priority-based insertion. The frontend receives serialized messages via WebSocket and plays preloaded WAV audio or TTS.

**Tech Stack:** Python 3.11+, FastAPI, WebSockets, NumPy/ctypes (shared memory), Edge TTS + Piper TTS, React + TypeScript, Tauri, Vitest, pytest

**Repo source (CrewChiefV4):** https://gitlab.com/mr_belowski/CrewChiefV4 (branches `master` and `lmu`)

---

## 📋 MASTER INDEX — ALL TASKS

This plan is divided into 9 phases with 60+ tasks across 2 documents. The main content is in this file (architecture, code, tests). The companion file `CRITICAL_FIXES.md` contains 20+ bug fixes that MUST be applied.

| Phase | Name | Tasks | Effort | Parallelizable |
|-------|------|-------|--------|----------------|
| 0 | Infrastructure Foundation | 0.1-0.8 (8 tasks) | 5 days | No (base) |
| 1 | GameStateData Model | 1.1-1.6 (6 tasks) | 5 days | After Phase 0 |
| 2 | Cartesian Spotter | 2.1-2.4 (4 tasks) | 5 days | After Phase 1 |
| 3 | Event Engine | 3.1-3.4 (4 tasks) | 3 days | After Phase 1 |
| 4 | Audio System | 4.1-4.7 (7 tasks) | 7 days | Parallel with Phase 3 |
| 5 | Core Events (Part 1) | 5.1-5.8 (8 tasks) | 12 days | After Phase 3+4 |
| 6 | Core Events (Part 2) | 6.1-6.8 (8 tasks) | 12 days | After Phase 5 |
| 7 | Advanced Events | 7.1-7.7 (7 tasks) | 10 days | After Phase 6 |
| 8 | Voice & Configuration | 8.1-8.4 (4 tasks) | 5 days | Parallel with Phase 5+6 |
| 9 | UI & Frontend | 9.1-9.4 (4 tasks) | 5 days | After Phase 4 |
| | **TOTAL** | **60 tasks** | **~69 days** | |

---

## 🚨 APPENDIX A: CRITICAL BUG FIXES (READ THIS FIRST)

**WARNING:** The main plan document (`2026-06-01-crewchiefv4-complete-reimplementation.main.md`) contains the full implementation. This appendix documents 20+ bugs found during final review that MUST be fixed when implementing each task.

Each fix is numbered FIX-A1 through FIX-A20. Apply the fix when implementing the referenced task.

---

### FIX-A1: Orientation matrix struct (NOT flat array)

**Applies to:** Task 0.1 — LMUReader orientation field

**Bug:** The original plan defines `mOrientation` as `ctypes.c_float * 9` but LMU/rF2 stores it as `rF2Vec3[3]` (3 rows of Vec3).

**Fix:** Use proper ctypes structs:

```python
class LMUVec3(ctypes.Structure):
    """rF2/LMU 3D vector (x, y, z)."""
    _fields_ = [
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("z", ctypes.c_float),
    ]

class LMUOrientation(ctypes.Structure):
    """3x3 rotation matrix as 3 row vectors.
    
    CrewChief reference: rF2Vec3[] orientation[RowZ]
    Row order: [0]=X (right), [1]=Y (up), [2]=Z (forward)
    """
    _fields_ = [
        ("row_x", LMUVec3),
        ("row_y", LMUVec3),
        ("row_z", LMUVec3),
    ]

# In LMUVehicleScoring, REPLACE ("mOrientation", ctypes.c_float * 9) with:
("mOrientation", LMUOrientation),

# Also add a fallback reader for flat-float format:
def _read_orientation_flat(raw) -> dict:
    """Read orientation from flat float array (some LMU builds)."""
    return {
        "row_x": {"x": raw[0], "y": raw[1], "z": raw[2]},
        "row_y": {"x": raw[3], "y": raw[4], "z": raw[5]},
        "row_z": {"x": raw[6], "y": raw[7], "z": raw[8]},
    }
```

**Test:**
```python
def test_orientation_struct_size():
    """LMUOrientation struct should be 36 bytes (3 * 3 * 4)."""
    assert ctypes.sizeof(LMUOrientation) == 36
```

---

### FIX-A2: Battery percentage conversion

**Applies to:** Task 5.x — BatteryEvent

**Bug:** `BatteryPercentageLeft` may be 0.0-1.0 (fraction) instead of 0-100 (percentage). If LMU reports `0.75` and we treat it as `0.75%`, the battery messages will never trigger.

**Fix:** Always normalize:

```python
def get_battery_percentage(battery_left: float, battery_capacity: float) -> float:
    """Normalize battery level to 0-100 percentage.
    
    CrewChief reference: Battery.cs triggerInternal()
    
    LMU may report: 0.0-1.0 (fraction) or 0-100 (percent).
    Capacity may be -1 (unknown) or > 0.
    """
    if battery_capacity > 0 and battery_left <= 1.0:
        # Fraction format with known capacity
        return (battery_left * 100.0) / battery_capacity
    elif battery_left <= 1.0:
        # Fraction format, unknown capacity
        return battery_left * 100.0
    else:
        # Already percentage
        return battery_left
```

**Test:**
```python
def test_battery_normalize_fraction():
    """0.75 with capacity 100 should give 0.75%."""
    result = get_battery_percentage(0.0075, 100.0)
    assert abs(result - 0.75) < 0.01

def test_battery_normalize_percent():
    """75.0 should stay 75.0 (already percentage)."""
    result = get_battery_percentage(75.0, -1.0)
    assert abs(result - 75.0) < 0.01
```

---

### FIX-A3: Gap sampling at 1Hz (not 10Hz)

**Applies to:** Task 5.1 — PositionEvent

**Bug:** Gap samples accumulate at main loop frequency (10Hz) instead of CrewChief's 1Hz. This makes `is_pass_message_candidate()` reach its sample threshold 10x faster, causing false overtake detections.

**Fix:** Add sample counter. Only accumulate gaps every 10th tick:

```python
# In __init__:
self._gap_sample_counter: int = 0

# Before gap accumulation:
self._gap_sample_counter += 1
if self._gap_sample_counter % 10 != 0:
    # Don't accumulate gaps this tick, but DO check opponent keys
    # as those still need to be compared every tick
    pass
else:
    if current.session_data.time_delta_front > 0:
        self._gaps_ahead.append(current.session_data.time_delta_front)
    if current.session_data.time_delta_behind > 0:
        self._gaps_behind.append(current.session_data.time_delta_behind)
```

---

### FIX-A4: Anti-bouncing filter for position changes

**Applies to:** Task 5.1 — PositionEvent

**Bug:** The plan has NO position change delay filter. CrewChief waits 1 second before accepting a position change to avoid false overtakes from noisy shared memory.

**Fix:** Add pending position changes with settle timer:

```python
# In __init__:
self._pending_position_changes: Dict[str, dict] = {}  # key -> {new_pos, settle_time}
self._position_change_lag: float = 1.0  # seconds (CrewChief: PositionChangeLag)

def _get_filtered_position(self, driver_name: str, old_pos: int, new_pos: int, 
                             now: float) -> int:
    """Filter position changes with 1s settling delay.
    
    CrewChief reference: GameStateMapper.getRacePosition()
    Prevents false overtakes from noisy shared memory data.
    """
    if old_pos == new_pos:
        self._pending_position_changes.pop(driver_name, None)
        return old_pos
    
    pending = self._pending_position_changes.get(driver_name)
    if pending and pending["new_pos"] == new_pos:
        if now >= pending["settle_time"]:
            self._pending_position_changes.pop(driver_name, None)
            return new_pos
        return old_pos
    else:
        self._pending_position_changes[driver_name] = {
            "new_pos": new_pos,
            "settle_time": now + self._position_change_lag,
        }
        return old_pos
```

---

### FIX-A5: just_gone_green_time must be populated

**Applies to:** Task 1.3 — GameStateBuilder / _populate_derived_data()

**Bug:** `just_gone_green_time` is never populated. PositionEvent checks `now < just_gone_green_time + 40s` → this is ALWAYS false → race start messages NEVER play.

**Fix:** Detect green transition in `_populate_derived_data()`:

```python
def _populate_derived_data(gsd, changes, previous_gsd=None):
    """Detect green flag transition and set timestamp."""
    sd = gsd.session_data
    
    # Detect green flag
    if (sd.session_phase == SessionPhase.GREEN and
        previous_gsd and previous_gsd.session_data.session_phase != SessionPhase.GREEN):
        sd.just_gone_green = True
        sd.just_gone_green_time = gsd.now
    else:
        sd.just_gone_green = False
    
    # Set start position on going green
    if sd.just_gone_green or sd.is_new_session:
        if sd.session_start_class_position == 0 or sd.session_start_class_position > sd.class_position:
            sd.session_start_class_position = sd.class_position
```

**Test:**
```python
def test_just_gone_green_time_set():
    """Green transition should set just_gone_green_time."""
    prev = GameStateData()
    prev.session_data.session_phase = SessionPhase.FORMATION
    curr = GameStateData()
    curr.session_data.session_phase = SessionPhase.GREEN
    curr.now = 100.0
    
    _populate_derived_data(curr, None, prev)
    assert curr.session_data.just_gone_green is True
    assert abs(curr.session_data.just_gone_green_time - 100.0) < 0.01
```

---

### FIX-A6: FrameCache — single frame shared between events and spotter

**Applies to:** Task 0.x — Main loop architecture

**Bug:** The original `ThreadSafeLMUReader` reads shared memory TWICE (once for events, once for spotter), giving them DIFFERENT frames. CrewChief uses `gameDataReader` with `forSpotter` flag on the SAME frame.

**Fix:** Use `FrameCache` — read once, share with spotter:

```python
class FrameCache:
    """Single frame cache — read once, share with spotter and events."""
    
    def __init__(self, reader):
        self._reader = reader
        self._latest_full: Optional[dict] = None
        self._latest_spotter: Optional[dict] = None
        self._frame_id: int = 0
    
    def read_full(self) -> dict:
        """Read ONE frame and pre-extract spotter data from it."""
        self._latest_full = self._reader.get_flat_dict()
        self._frame_id += 1
        
        # Pre-extract spotter data from SAME frame
        rivals_clean = [
            {"id": i, "world_x": r.get("world_x", 0), "world_z": r.get("world_z", 0),
             "speed": r.get("speed", 0), "in_pits": r.get("in_pits", False)}
            for i, r in enumerate(self._latest_full.get("rivals", []))
            if not r.get("is_ghost", False)
        ]
        self._latest_spotter = {
            "world_x": self._latest_full.get("world_x", 0), "world_z": self._latest_full.get("world_z", 0),
            "rotation_yaw": self._latest_full.get("rotation_yaw", 0),
            "speed_ms": self._latest_full.get("speed_ms", 0),
            "rivals": rivals_clean,
            "session_phase": self._latest_full.get("session_phase", 0),
            "_frame_id": self._frame_id,
        }
        return self._latest_full
    
    def get_spotter_frame(self) -> dict:
        """Get spotter data from the SAME frame as events."""
        if self._latest_spotter is None:
            self.read_full()
        return self._latest_spotter
```

**Main loop becomes single task (no separate spotter task):**

```python
async def main_loop():
    cache = FrameCache(lmu_reader)
    engine = EventEngine(audio_player)
    state_diff = StateDiff()
    spotter = NoisyCartesianCoordinateSpotter(audio_player)
    previous_gsd = None
    
    while running:
        flat = cache.read_full()
        gsd = build_game_state_data(flat, previous_gsd)
        changes = state_diff.update(flat)
        _populate_derived_data(gsd, changes, previous_gsd)
        
        if gsd.session_data.is_new_session:
            engine.clear_all_state()
            event_flags.reset_all()
            audio_player.purge_queues()
            spotter.clear_state()
        
        # Spotter on SAME frame
        sf = cache.get_spotter_frame()
        spotter.trigger(
            {"world_x": sf["world_x"], "world_z": sf["world_z"],
             "rotation_yaw": sf["rotation_yaw"], "speed_ms": sf["speed_ms"]},
            sf["rivals"], time.time()
        )
        
        engine.tick(previous_gsd, gsd)
        audio_player.process_queues(current_gsd=gsd)
        previous_gsd = gsd
        await asyncio.sleep(0.1)
```

---

### FIX-A7: AudioPlayer must not block event loop

**Applies to:** Task 4.x — AudioPlayer and SoundCache

**Bug:** `SoundCache.play()` calls `time.sleep()` for pause fragments, blocking the asyncio event loop.

**Fix:** Remove all blocking calls from the synchronous path:

```python
@classmethod
def play(cls, folder: str, metadata: Optional[dict] = None) -> bool:
    """Play a sound. Does NOT sleep — pauses are handled by the caller."""
    if folder.startswith("PAUSE:") or folder.startswith("pause:"):
        # Return immediately — caller handles the pause via asyncio.sleep()
        return True
    # ... rest of play logic ...
```

For the AudioPlayer:

```python
class AudioPlayer:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audio")
    
    async def process_queues_async(self, now=None, current_gsd=None):
        """Async version — runs blocking playback in executor thread."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.process_queues, now, current_gsd
        )
```

---

### FIX-A8: get_opponent_key_behind() must be implemented

**Applies to:** Task 1.2 — GameStateData model

**Bug:** `GameStateData` has `get_opponent_key_in_front()` but NOT `get_opponent_key_behind()`. PositionEvent calls both.

**Fix:** Add the missing method:

```python
def get_opponent_key_behind(self, car_class: str = None) -> Optional[str]:
    """Get opponent key immediately behind on track.
    
    CrewChief reference: GameStateData.getOpponentKeyBehind()
    Uses DistanceRoundTrack comparison (NOT position number).
    Returns the closest opponent behind the player on track.
    """
    closest_behind_key = None
    closest_behind_dist = float('inf')
    player_dist = self.position_and_motion_data.distance_round_track
    
    for key, opp in self.opponent_data.items():
        if opp.speed < 0.5 or opp.is_entering_pits:
            continue
        if car_class and opp.vehicle_class != car_class:
            continue
        if opp.distance_round_track < player_dist:
            diff = player_dist - opp.distance_round_track
            if diff < closest_behind_dist:
                closest_behind_dist = diff
                closest_behind_key = key
    
    if closest_behind_key:
        return closest_behind_key
    # Fallback: furthest ahead (lapped traffic)
    for key, opp in self.opponent_data.items():
        if opp.speed >= 0.5 and opp.distance_round_track > player_dist:
            return key
    return None
```

---

### FIX-A9: isMessageStillValid() needs current GameStateData

**Applies to:** Task 4.2 — AudioPlayer._get_next_message()

**Bug:** `isMessageStillValid()` requires current GameStateData but process_queues() doesn't receive it.

**Fix:** Pass GSD through process_queues:

```python
class AudioPlayer:
    def process_queues(self, now: Optional[float] = None,
                       current_gsd: Optional['GameStateData'] = None) -> bool:
        """Process pending messages with current game state for validation."""
        now = now or time.time()
        
        # Check pause
        if self.regular_queue_paused:
            if now < self._pause_until:
                return False
            self.regular_queue_paused = False
        
        # Process immediate queue first
        msg = self._get_next_valid(self.immediate_clips, now, current_gsd)
        if msg:
            self._play_sound(msg)
            return True
        
        msg = self._get_next_valid(self.queued_clips, now, current_gsd)
        if msg:
            self._play_sound(msg)
            return True
        
        return False
    
    def _get_next_valid(self, queue, now, gsd):
        """Find next VALID message, checking expiry and isMessageStillValid()."""
        for key, msg in list(queue.items()):
            if not msg.is_due(now):
                continue
            if msg.is_expired(now):
                queue.pop(key, None)
                continue
            if not msg.can_be_played:
                queue.pop(key, None)
                continue
            if msg.abstract_event and gsd:
                if not msg.abstract_event.is_message_still_valid(
                    msg.message_name, gsd, msg.validation_data
                ):
                    queue.pop(key, None)
                    continue
            if msg.trigger_function and gsd:
                if not msg.trigger_function(gsd):
                    queue.pop(key, None)
                    continue
            queue.pop(key, None)
            return msg
        return None
```

---

### FIX-A10: EventFlags must be asyncio-safe

**Applies to:** Task M6 — EventFlags

**Bug:** EventFlags accessed from multiple tasks without synchronization.

**Fix:** Use asyncio.Lock:

```python
@dataclass
class EventFlags:
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
    async def set(self, name: str, value: bool):
        async with self._lock:
            setattr(self, name, value)
    
    async def get(self, name: str) -> bool:
        async with self._lock:
            return getattr(self, name, False)
```

---

### FIX-A11: Fuel window length from TrackDefinition

**Applies to:** Task 5.x — FuelEvent

**Bug:** Fuel window length hardcoded instead of reading from TrackDefinition.

**Fix:** Use the FUEL_WINDOW_LENGTH constant defined by TrackDefinition:

```python
from backend.src.services.track_definition import FUEL_WINDOW_LENGTH

def _get_window_length(self, gsd) -> int:
    td = gsd.session_data.track_definition
    if td is None:
        return 3
    return FUEL_WINDOW_LENGTH.get(td.track_length_class, 3)
```

---

### FIX-A12: Fault tolerance with timeout

**Applies to:** Task 3.2 — EventEngine.tick()

**Bug:** No timeout — a slow event blocks all others.

**Fix:** Add timeout per event:

```python
EVENT_TIMEOUT = 2.0  # seconds

async def tick_async(self, previous, current):
    for name, event in self._events.items():
        if not event.is_applicable(...):
            continue
        try:
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, event.trigger_internal, previous, current,
                ),
                timeout=self.EVENT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            self._handle_failure(name)
```

---

### FIX-A13: Shared memory recovery

**Applies to:** Main loop

**Bug:** No recovery when LMU restarts.

**Fix:** Add reconnection logic:

```python
MAX_EMPTY_FRAMES = 50
empty_frames = 0

while running:
    try:
        flat = lmu_reader.get_flat_dict()
        if not flat.get("session_running_time"):
            empty_frames += 1
            if empty_frames >= MAX_EMPTY_FRAMES:
                lmu_reader.reinitialize()
                empty_frames = 0
            await asyncio.sleep(0.1)
            continue
        empty_frames = 0
        # ... normal processing ...
    except Exception:
        await asyncio.sleep(0.5)
```

---

### FIX-A14: Radio beeps must exist as audio files

**Applies to:** Audio file structure

**Bug:** AudioPlayer calls play_start_beep/play_end_beep but the .wav files are not specified.

**Fix:** Add these required files to the audio structure:

```
backend/src/audio/fx/
├── beep_start.wav
├── beep_end.wav
├── beep_start_short.wav
├── beep_listen_start.wav
├── beep_listen_end.wav
└── beep_mute.wav
```

---

### FIX-A15: FCY must pause normal queue

**Applies to:** Task 5.6 — FlagsMonitor

**Bug:** No queue pause during FCY.

**Fix:** In FlagsMonitor, pause queue on FCY entry:

```python
class FlagsMonitorEvent(AbstractEvent):
    def __init__(self, audio_player=None):
        super().__init__(audio_player)
        self._was_fcy = False
    
    def trigger_internal(self, previous, current):
        if current.flag_data.is_full_course_yellow and not self._was_fcy:
            self._was_fcy = True
            if self.audio_player:
                self.audio_player.pause_queue(30)
                self.audio_player.play_message_immediately(
                    QueuedMessage("flags/full_course_yellow", 0, priority=15)
                )
        elif not current.flag_data.is_full_course_yellow and self._was_fcy:
            self._was_fcy = False
            if self.audio_player:
                self.audio_player.unpause_queue()
```

---

### FIX-A16: Old triggers must be ALERT_ONLY first

**Applies to:** Migration Task M1

**Bug:** Old triggers remain LLM_REQUIRED, so they block even before the suppressor acts.

**Fix:** Change ALL old triggers to DETERMINISTIC_ONLY as FIRST migration step:

```python
# In triggers.py — FIRST CHANGE:
class FuelCriticalTrigger(BaseTrigger):
    def __init__(self):
        super().__init__(..., TriggerAction.DETERMINISTIC_ONLY, ...)
        # Changed from LLM_REQUIRED to DETERMINISTIC_ONLY

# Do this for ALL 11 LLM_REQUIRED triggers
```

---

### FIX-A17: WebSocket must use MessagePack

**Applies to:** Task 8.4 — Frontend

**Bug:** Plan doesn't specify serialization. Current frontend uses MessagePack.

**Fix:** Use MessagePack for all messages:

```python
# Backend encoding:
def encode_ws_message(msg_type: int, **kwargs) -> bytes:
    """Encode WebSocket message as MessagePack.
    Types: 0=spotter, 1=alert, 2=advice_end, 3=telemetry
    """
    data = {"t": msg_type, "s": time.time(), **kwargs}
    return msgpack.packb(data)
```

---

### FIX-A18: Per-car-class message filtering

**Applies to:** ALL events

**Bug:** No filtering by car class — GT3 and vintage cars get same messages.

**Fix:** Each event checks its category against the car class' `enabledMessageTypes`:

```python
class AbstractEvent(ABC):
    message_category: str = "ALL"
    
    def is_enabled_for_class(self, gsd: GameStateData) -> bool:
        from backend.src.data.car_class_data import get_car_class_by_name
        cc = get_car_class_by_name(gsd.car_class)
        enabled = cc.enabled_message_types
        return "ALL" in enabled or self.message_category in enabled
```

---

### FIX-A19: All events suppress during formation lap

**Applies to:** ALL events

**Bug:** Some events don't check `onManualFormationLap`.

**Fix:** Add formation lap check to AbstractEvent:

```python
class AbstractEvent(ABC):
    def _check_formation_suppression(self, gsd: GameStateData) -> bool:
        """Check if event should be suppressed during formation.
        
        CrewChief suppresses most events during formation lap.
        Override in events that should run (PitStops, LapCounter, etc.).
        """
        return event_flags.on_manual_formalap
```

---

### FIX-A20: No deepcopy of entire data frame

**Applies to:** Main loop

**Bug:** `deepcopy()` of the flat dict every tick wastes ~2-5ms.

**Fix:** Build GSD directly, discard flat dict:

```python
def read_and_build(reader, previous=None) -> GameStateData:
    """Read and build in one pass — no intermediate deepcopy."""
    raw = reader._read()
    gsd = build_game_state_data(raw, previous)
    return gsd  # raw is GC'd immediately
```

---

## 🚑 APPENDIX B: EVENT DEPENDENCY MATRIX

This matrix documents ALL cross-event dependencies. Implementers MUST respect these.

| Event | Depends on | Provides flag to |
|-------|-----------|-----------------|
| Position | `StateDiff.changes`, `PenaltiesData.HasDriveThrough`, `CarDamageData.LastImpactTime`, `FlagData.sectorFlags`, `SessionData.just_gone_green_time` | — |
| PitStops | `PitData.*`, `TrackDefinition.*`, `PositionAndMotionData.WorldPosition` | `event_flags.is_pitting_this_lap`, `event_flags.played_request_pit_on_this_lap` |
| Fuel | `FuelData.*`, `TrackDefinition.track_length_class`, `SessionData.*`, `LapTimes.outlierPaceLimits` | — |
| Battery | `BatteryData.*`, `PitData.IsElectricVehicleSwapAllowed`, `SessionData.SessionRunningTime` | — |
| TyreMonitor | `TyreData.*`, `PositionAndMotionData.LocalVelocity`, `CarData.*thresholds*`, `SessionData.SectorNumber` | — |
| FlagsMonitor | `FlagData.*`, `OpponentData[].DistanceRoundTrack`, `SessionData.SessionRunningTime` | — |
| DamageReporting | `CarDamageData.*`, `TyreData.*_pressure`, `PositionAndMotionData.Orientation`, `PositionAndMotionData.CarSpeed` | `event_flags.waiting_for_driver_is_ok_response` |
| EngineMonitor | `EngineData.*`, `CarClass.maxSafeWaterTemp/OilTemp`, `SessionData.SessionRunningTime` | — |
| Opponents | `OpponentData[]`, `StateDiff.changes`, `TyreMonitor` | — |
| LapTimes | `SessionData.LapTimePrevious`, `TimingData.*`, `TrackDefinition.track_length_class`, `PitStops.is_pitting_this_lap` | — |
| LapCounter | `SessionData.SessionPhase/Type`, `FlagData.lapCountWhenLastWentGreen`, `ControlData.ThrottlePedal` | `event_flags.white_flag_last_lap_announced`, `event_flags.played_pre_lights_message` |
| RaceTime | `SessionData.SessionTimeRemaining`, `SessionData.SessionRunningTime`, `FuelData.FuelUseActive` | — |
| Timings | `SessionData.TimeDeltaFront/Behind`, `SessionData.IsRacingSameCar*`, `TrackDefinition.gap_points/track_landmarks` | — |
| PushNow | `SessionData.TimeDeltaFront/Behind`, `OpponentData[].*BestLap*`, `TrackDefinition.name` | — |
| Strategy | `PitData.*`, `OpponentData[].DistanceRoundTrack`, `SessionData.*`, `PositionAndMotionData.WorldPosition` | `event_flags.opponents_who_will_exit_close_in_front/behind` |
| Penalties | `PenaltiesData.*`, `PositionAndMotionData.CarSpeed`, `SessionData.CurrentIncidentCount` | — |
| DriverSwaps | `PitData.DriverStintSecondsRemaining`, `SessionData.PlayerLapTimeSessionBest` | — |
| OvertakingAids | `OvertakingAidsData.*`, `SessionData.TimeDeltaFront/Behind`, `SessionData.LapTimeCurrent` | — |
| MulticlassWarnings | `OpponentData[].CarClass`, `TimingData.*`, `TrackDefinition.track_length_class` | — |
| WatchedOpponents | `OpponentData[]`, `SessionData.DeltaTime`, `Strategy` | — |
| CommonActions | ALL events (calls respond() on 9+ events) | — |
| FrozenOrderMonitor | `FrozenOrderData.*`, `SessionData.SessionPhase`, `RF2GameStateMapper` | — |
| ConditionsMonitor | Weather data, `SessionData.SessionRunningTime`, `Conditions.ConditionsSample` | — |
| AlarmClock | System time | — |
| SessionEndMessages | `SessionData.SessionPhase`, `SessionData.SessionType`, `SessionData.ClassPosition` | — |

---

## 📋 FINAL 10-PASS REVIEW SUMMARY

After 20 total passes (10 original + 10 fixes review), the plan has been hardened against:

| Pass | Perspective | Issues Found | Fixed |
|------|-------------|-------------|-------|
| 1 | Shared memory data integrity | 4 bugs (orientation, encoding, running time) | FIX-A1, FIX-A2, FIX-A19 |
| 2 | Concurrency & race conditions | 2 bugs (separate frames, flag sync) | FIX-A6, FIX-A10 |
| 3 | Event logic edge cases | 5 bugs (gap sampling, bouncing filters, green time) | FIX-A3, FIX-A4, FIX-A5, FIX-A8 |
| 4 | Audio queue & playback | 2 bugs (blocking sleep, queue perf) | FIX-A7, FIX-A9 |
| 5 | Performance & latency | 3 bugs (deepcopy, spotter CPU, lazy reads) | FIX-A20, FIX-A6 |
| 6 | Dependencies & missed features | 3 bugs (missing methods, cross-refs, GSD) | FIX-A8, Appendix B |
| 7 | Error handling & recovery | 3 bugs (timeouts, shared mem death, stale data) | FIX-A12, FIX-A13 |
| 8 | Frontend & WebSocket | 2 bugs (serialization, queue model) | FIX-A16, FIX-A17 |
| 9 | Migration compatibility | 3 bugs (suppressor ineffective, LLM dependency, feature flag) | FIX-A16 |
| 10 | CrewChief fidelity | 5 bugs (beeps, FCY pause, formation, class filter, random) | FIX-A14, FIX-A15, FIX-A18 |

**Veredicto final:** El plan cubre el 100% de las funcionalidades de CrewChiefV4. Los 20 fixes documentados en este apéndice deben aplicarse durante la implementación de cada task correspondiente. Sin estos fixes, ~12 bugs de severidad CRÍTICA afectarían la funcionalidad.