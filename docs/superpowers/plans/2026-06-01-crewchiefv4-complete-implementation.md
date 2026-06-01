# CrewChiefV4 Complete Implementation Plan — CORRECTED VERSION

> **Target:** Fresh model executing in a separate chat. This is your ONLY reference — all bugs from the previous plan v1 have been fixed inline.

**Goal:** Replicate 100% of CrewChiefV4 for Le Mans Ultimate in Vantare Ingeniero — deterministic Cartesian spotter, 29 event classes, dual-priority audio queue, 70+ voice commands, complete battery/hybrid (LMU WEC), driver swaps, timing/gaps, penalties, damage, tyres, engine, fuel, pit stops, formation, multiclass, watched opponents, session end, pearls. VR overlay excluded.

**Architecture:** Python asyncio backend (FastAPI) + TypeScript frontend (Tauri/React). Backend reads LMU shared memory via ctypes (one FrameCache shared between events and spotter). Single main loop at 10Hz produces GameStateData → EventEngine dispatches to 29 events → AudioPlayer dual queue → WebSocket to frontend. Spotter runs INLINE in main loop (not separate task). All events fault-tolerant with 2s timeout and 10-failure disable.

**Tech Stack:** Python 3.11+, FastAPI, WebSockets, ctypes (shared memory), asyncio, Edge TTS + Piper TTS, React + TypeScript, Tauri, Vitest, pytest

**Repo source (CrewChiefV4):** https://gitlab.com/mr_belowski/CrewChiefV4 (branches `master` and `lmu`)

---

## 📋 COMPLETE FILE INVENTORY

```
backend/src/
├── main.py                          (main loop with FrameCache)
├── config/
│   ├── settings.py                  (200+ settings, feature flags)
│   ├── global_behaviour.py          (mutable runtime flags)
│   └── user_settings.py             (profile system, JSON persistence)
├── models/
│   ├── enums.py                     (SessionType, SessionPhase, FlagEnum, etc.)
│   ├── game_state_data.py           (30+ dataclasses, unified state)
│   └── messages.py                  (QueuedMessage, MessageFragment, DelayedMessageEvent)
├── services/
│   ├── lmu_reader.py                (ctypes shared memory reader)
│   ├── game_state_builder.py        (flat dict → GameStateData)
│   ├── state_diff.py                (PreviousTick change detection)
│   ├── track_definition.py          (length class, gap points, landmarks)
│   ├── delta_time.py                (lap-difference-aware deltas)
│   ├── frame_cache.py               (single frame for events + spotter)
│   ├── audio_player.py              (dual queue, priority, async executor)
│   ├── sound_cache.py               (available sounds, variety, TTS)
│   ├── number_reader.py             (integer/time reading)
│   ├── playback_moderator.py        (message filtering rules)
│   ├── colloquial_time.py           (natural time: "quarter past")
│   └── utilities.py                 (random, WholeAndFractionalPart)
├── intelligence/
│   ├── base_event.py                (AbstractEvent base class)
│   ├── event_engine.py              (dispatch, fault tolerance, timeout)
│   ├── event_flags.py               (cross-event shared state, asyncio-safe)
│   ├── trigger_to_event_bridge.py   (migration from old triggers)
│   ├── noisy_cartesian_spotter.py   (full Cartesian spotter)
│   └── events/
│       ├── position.py              (overtakes, race start, reminders)
│       ├── pit_stops.py             (countdown, limiter, mandatory stops)
│       ├── fuel.py                  (consumption, windows, FCY)
│       ├── battery.py               (LMU WEC VE management)
│       ├── tyre_monitor.py          (temps by compound, wear, locking)
│       ├── flags_monitor.py         (FCY 7 phases, blue flag, incident)
│       ├── damage_reporting.py      (5 components, puncture, rollover)
│       ├── engine_monitor.py        (oil/water temps, stall)
│       ├── opponents.py             (leader changes, retirements)
│       ├── lap_times.py             (sector deltas, consistency)
│       ├── lap_counter.py           (pre-lights, last lap, formation)
│       ├── race_time.py             (time remaining announcements)
│       ├── timings.py               (gap status, attack/defend spots)
│       ├── push_now.py              (strategic push, pit exit)
│       ├── strategy.py              (post-pit prediction, benchmark)
│       ├── penalties.py             (cut track, drive-through, DSQ)
│       ├── multiclass_warnings.py   (faster/slower class)
│       ├── watched_opponents.py     (driver tracking)
│       ├── session_end_messages.py  (win/podium/last/rant)
│       ├── driver_swaps.py          (LMU WEC stint management)
│       ├── overtaking_aids.py       (DRS, Push-to-Pass)
│       ├── conditions_monitor.py    (weather, track temp)
│       ├── frozen_order_monitor.py  (SC, formation, rolling start)
│       ├── common_actions.py        (orchestrator)
│       └── alarm_clock.py           (time alarms)
├── data/
│   └── car_class_data.py            (120+ car classes, thresholds)
└── audio/                           (WAV files organized by event/category)
    ├── spotter/, position/, pit_stops/, fuel/, battery/, ...
    ├── fx/beep_start.wav, beep_end.wav, ...
    └── driver_names/                (pilot name WAV files)
```

---

## 🔴 CRITICAL: CROSS-EVENT DEPENDENCIES (read this before implementing any event)

| Event | Depends On | Provides Flag For |
|-------|-----------|-----------------|
| **Position** | `StateDiff.changes.position_changed`, `PenaltiesData.HasDriveThrough`, `CarDamageData.LastImpactTime`, `FlagData.sectorFlags`, `SessionData.just_gone_green_time` | — |
| **PitStops** | `PitData.*`, `TrackDefinition.pit_entry_point`, `PositionAndMotionData.WorldPosition`, `PositionAndMotionData.DistanceRoundTrack` | `event_flags.is_pitting_this_lap`, `event_flags.played_request_pit_on_this_lap`, `event_flags.waiting_for_mandatory_stop_timer` |
| **Fuel** | `FuelData.FuelLeft`, `FuelData.FuelUseActive`, `TrackDefinition.track_length_class`, `SessionData.SessionLapsRemaining`, `SessionData.SessionRunningTime`, `FlagData.is_full_course_yellow` | — |
| **Battery** | `BatteryData.BatteryPercentageLeft`, `BatteryData.BatteryCapacity`, `BatteryData.BatteryUseActive`, `PitData.IsElectricVehicleSwapAllowed`, `SessionData.SessionRunningTime`, `TrackDefinition.track_length_class` | — |
| **TyreMonitor** | `TyreData.*`, `PositionAndMotionData.LocalVelocity`, `CarData.get_tyre_temp_thresholds()`, `CarData.get_brake_temp_thresholds()`, `SessionData.SectorNumber`, `SessionData.IsNewLap` | — |
| **FlagsMonitor** | `FlagData.*`, `OpponentData[].DistanceRoundTrack`, `OpponentData[].Speed`, `SessionData.SessionRunningTime`, `PositionAndMotionData.DistanceRoundTrack` | — |
| **DamageReporting** | `CarDamageData.*`, `TyreData.*_pressure`, `PositionAndMotionData.Orientation`, `PositionAndMotionData.CarSpeed`, `PositionAndMotionData.LocalAcceleration`, `SessionData.SessionRunningTime`, `SessionData.SessionPhase` | `event_flags.waiting_for_driver_is_ok_response` |
| **EngineMonitor** | `EngineData.*`, `CarClass.maxSafeWaterTemp`, `CarClass.maxSafeOilTemp`, `SessionData.SessionRunningTime`, `SessionData.SessionType`, `PitData.InPitlane` | — |
| **Opponents** | `OpponentData[]`, `StateDiff.changes.leader_changed/retired_drivers`, `SessionData.ClassPosition`, `SessionData.CompletedLaps`, `TyreMonitor` (for tyre changes) | — |
| **LapTimes** | `SessionData.LapTimePrevious/Current`, `SessionData.IsNewLap/Sector`, `TimingData.*`, `TrackDefinition.track_length_class`, `PitData.InPitlane` | — |
| **LapCounter** | `SessionData.SessionPhase/Type`, `SessionData.CompletedLaps/IsNewLap`, `FlagData.lapCountWhenLastWentGreen`, `ControlData.ThrottlePedal`, `PitData.*`, `OpponentData[].PositionAndMotionData` | `event_flags.white_flag_last_lap_announced`, `event_flags.played_pre_lights_message`, `event_flags.pre_start_temps_announced` |
| **RaceTime** | `SessionData.SessionTimeRemaining/RunningTime`, `SessionData.SessionHasFixedTime`, `FuelData.FuelUseActive`, `OpponentData[].CompletedLaps/ClassPosition` | — |
| **Timings** | `SessionData.TimeDeltaFront/Behind`, `SessionData.IsRacingSameCar*`, `TrackDefinition.gap_points/landmarks`, `SessionData.CompletedLaps`, `PositionAndMotionData.DistanceRoundTrack` | — |
| **PushNow** | `SessionData.TimeDeltaFront/Behind`, `SessionData.SessionTimeRemaining`, `OpponentData[].*BestLap*`, `TrackDefinition.name/length`, `PositionAndMotionData.DistanceRoundTrack` | — |
| **Strategy** | `PitData.*`, `OpponentData[].DistanceRoundTrack/Speed/ClassPosition/InPits`, `SessionData.*`, `PositionAndMotionData.WorldPosition` | `event_flags.opponents_who_will_exit_close_in_front/behind` |
| **Penalties** | `PenaltiesData.*`, `PositionAndMotionData.CarSpeed`, `SessionData.CurrentIncidentCount/MaxIncidentCount`, `SessionData.SessionType/Phase`, `PitData.*`, `ControlData.ControlType` | — |
| **DriverSwaps** | `PitData.DriverStintSecondsRemaining`, `SessionData.PlayerLapTimeSessionBest`, `SessionData.IsNewLap`, `PitData.InPitlane` | — |
| **OvertakingAids** | `OvertakingAidsData.*`, `SessionData.TimeDeltaFront/Behind/LapTimeCurrent`, `TrackDefinition.track_length`, `SessionData.IsNewLap`, `PositionAndMotionData.DistanceRoundTrack` | — |
| **MulticlassWarnings** | `OpponentData[].CarClass/ClassPosition/Speed/DistanceRoundTrack`, `TimingData.*`, `TrackDefinition.track_length_class`, `SessionData.CompletedLaps/RunningTime/ClassPosition` | — |
| **WatchedOpponents** | `OpponentData[]`, `SessionData.DeltaTime`, `Strategy.opponentsWhoWillExitClose...`, `PitData.InPitlane/IsAtPitExit` | — |
| **SessionEndMessages** | `SessionData.SessionPhase/Type/ClassPosition/SessionRunningTime/CompletedLaps/expectedFinishingPosition`, `SessionData.IsDisqualified/IsDNF` | — |
| **CommonActions** | ALL events (calls respond() on 9+ events) | — |
| **FrozenOrderMonitor** | `FrozenOrderData.*`, `SessionData.SessionPhase`, `PositionAndMotionData.CarSpeed`, `OpponentData[]` | — |
| **ConditionsMonitor** | Weather data (track/ambient temp, rain), `SessionData.SessionRunningTime` | — |
| **AlarmClock** | System time (`datetime.now`) | — |
| **Spotter** | `PositionAndMotionData.Orientation.Yaw/WorldPosition/CarSpeed`, `OpponentData[].Speed/WorldPosition` | `spotter.has_overlap` |

---

## 🔴 MAIN LOOP — CORRECTED (single loop, no separate spotter task)

**Bug fix:** Original plan had separate event loop and spotter loop → race conditions. CrewChief reads ONE frame and calls `spotter.trigger(lastState, currentState, gameStateData)` from the main loop. Spotter runs at `spotterInterval` (NOT separate thread in our case since we're at 10Hz, which is adequate for 20Hz equivalent).

**File:** `backend/src/main.py`

```python
import asyncio
import time
import logging
from typing import Optional

from backend.services.frame_cache import FrameCache
from backend.services.lmu_reader import LMUReader
from backend.services.game_state_builder import build_game_state_data, _populate_derived_data
from backend.services.state_diff import StateDiff
from backend.intelligence.event_engine import EventEngine
from backend.intelligence.base_event import FakeAudioPlayer  # Use real AudioPlayer in prod
from backend.intelligence.event_flags import event_flags
from backend.intelligence.noisy_cartesian_spotter import NoisyCartesianCoordinateSpotter
from backend.config.global_behaviour import global_settings

logger = logging.getLogger("vantare.main")

# ============================================================
# FRAME CACHE — Read once, share between events and spotter
# ============================================================
class FrameCache:
    """Single frame cache.
    
    CrewChief reference: gameDataReader.ReadGameData() — reads one frame,
    returns different data subsets based on forSpotter flag.
    
    CRITICAL: Events and spotter MUST operate on the SAME frame.
    A separate spotter loop reading different frames causes:
    - Spotter sees overtake 50ms before Position event
    - Discrepancy between spotter.has_overlap and actual position
    """
    
    def __init__(self, reader: LMUReader):
        self._reader = reader
        self._latest_full: Optional[dict] = None
        self._latest_spotter: Optional[dict] = None
        self._frame_id: int = 0
        self._last_telem_et: float = -1.0  # Dedup: skip if frame unchanged
    
    def read_full(self) -> dict:
        """Read ONE frame. Skip if shared memory hasn't updated."""
        raw = self._reader.get_flat_dict()
        
        # Skip unchanged frames (CrewChief: check mTelemetryET)
        current_et = raw.get("session_running_time", 0.0)
        if current_et == self._last_telem_et and self._latest_full is not None:
            return self._latest_full
        self._last_telem_et = current_et
        
        self._latest_full = raw
        self._frame_id += 1
        
        # Pre-extract spotter data from SAME frame
        rivals_clean = [
            {"id": i, "world_x": r.get("world_x", 0.0), "world_z": r.get("world_z", 0.0),
             "speed": r.get("speed", 0.0), "in_pits": r.get("in_pits", False),
             "is_ghost": r.get("is_ghost", False)}
            for i, r in enumerate(raw.get("rivals", []))
            if not r.get("is_ghost", False)
        ]
        self._latest_spotter = {
            "world_x": raw.get("world_x", 0.0), "world_z": raw.get("world_z", 0.0),
            "rotation_yaw": raw.get("rotation_yaw", 0.0),
            "speed_ms": raw.get("speed_ms", 0.0),
            "rivals": rivals_clean,
            "session_phase": raw.get("session_phase", 0),
            "in_pits": raw.get("in_pits", False),
            "lap_distance": raw.get("lap_distance", 0.0),
            "_frame_id": self._frame_id,
        }
        return self._latest_full
    
    def get_spotter_frame(self) -> dict:
        """Get spotter data from the SAME frame as events."""
        if self._latest_spotter is None:
            self.read_full()
        return self._latest_spotter


# ============================================================
# MAIN LOOP
# ============================================================
async def main_loop(reader: LMUReader, engine: EventEngine, audio_player):
    """Single main loop at 10Hz.
    
    CrewChief reference: CrewChief.cs:Run()
    
    Reads ONE frame, shares between spotter and events.
    Spotter runs INLINE (not separate task).
    Events have 2s timeout — slow events auto-disable after 10 failures.
    """
    cache = FrameCache(reader)
    state_diff = StateDiff()
    spotter = NoisyCartesianCoordinateSpotter(audio_player)
    spotter.clear_state()
    previous_gsd = None
    consecutive_empty_frames = 0
    max_empty_frames = 50  # ~5 seconds
    
    while True:
        try:
            # 1. Read ONE frame
            flat = cache.read_full()
            
            # 2. Check frame validity (game may have closed)
            if not flat.get("session_running_time", 0):
                consecutive_empty_frames += 1
                if consecutive_empty_frames >= max_empty_frames:
                    logger.warning("No data for 5s — attempting shared memory reinit")
                    _reinitialize_shared_memory(reader, cache)
                    consecutive_empty_frames = 0
                await asyncio.sleep(0.1)
                continue
            consecutive_empty_frames = 0
            
            # 3. Build GameStateData (NO deepcopy — direct from flat dict)
            gsd = build_game_state_data(flat, previous_gsd)
            
            # 4. Detect state changes
            changes = state_diff.update(flat)
            
            # 5. Populate derived session data (just_gone_green_time, etc.)
            _populate_derived_data(gsd, changes, previous_gsd)
            
            # 6. Handle session transitions
            if gsd.session_data.is_new_session:
                engine.clear_all_state()
                event_flags.reset_all()
                audio_player.purge_queues()
                spotter.clear_state()
                global_settings.complaints_count_in_this_session = 0
            
            # 7. Run spotter on SAME frame (inline, not separate task)
            if not event_flags.waiting_for_driver_is_ok_response:
                sf = cache.get_spotter_frame()
                if sf["session_phase"] == 6:  # FullCourseYellow
                    spotter._close_channel_if_idle(time.time())
                else:
                    spotter.trigger(sf, sf["rivals"], time.time())
            
            # 8. Dispatch events (with timeout)
            await engine.tick_async(previous_gsd, gsd)
            
            # 9. Process audio (with current GSD for validation)
            audio_player.process_queues(current_gsd=gsd)
            
            previous_gsd = gsd
            await asyncio.sleep(0.1)  # 10Hz
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            await asyncio.sleep(1.0)


def _reinitialize_shared_memory(reader, cache):
    """Reinit after game restart.
    
    CrewChief reference: gameDataReader.Initialise()
    """
    try:
        import subprocess
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq LMU.exe'],
            capture_output=True, text=True, timeout=5
        )
        if 'LMU.exe' not in result.stdout:
            logger.info("LMU not running — waiting for restart")
            return
    except Exception:
        pass
    
    reader._shmm = reader._create_mmap()
    reader._is_initialized = True
    cache._last_telem_et = -1.0
    cache._latest_full = None
    logger.info("Shared memory reinitialized")
```

---

## 🔴 EVENT ENGINE — CORRECTED (timeout + GSD validation)

**File:** `backend/src/intelligence/event_engine.py`

```python
import asyncio
import logging
from typing import Dict, Optional
from backend.models.game_state_data import GameStateData
from backend.intelligence.base_event import AbstractEvent

logger = logging.getLogger("vantare.event_engine")


class EventEngine:
    """Central event dispatcher with timeout and fault tolerance.
    
    CrewChief reference: CrewChief.cs triggerEvent()
    Each event has 2 seconds to execute. After 10 timeouts/failures,
    the event is disabled for the session.
    """
    
    MAX_FAILURES_BEFORE_DISABLE = 10
    EVENT_TIMEOUT = 2.0  # seconds
    
    def __init__(self, audio_player=None):
        self._events: Dict[str, AbstractEvent] = {}
        self._faulting_events: Dict[str, int] = {}
        self._session_has_failing_event = False
        self.audio_player = audio_player
    
    def register_event(self, name: str, event: AbstractEvent):
        self._events[name] = event
        logger.info(f"Registered: {name}")
    
    def clear_all_state(self):
        for name, event in self._events.items():
            try:
                event.clear_state()
            except Exception as e:
                logger.error(f"Error clearing {name}: {e}")
        self._faulting_events.clear()
        self._session_has_failing_event = False
    
    async def tick_async(self, previous: Optional[GameStateData], current: GameStateData):
        """Tick ALL applicable events with timeout."""
        if current is None:
            return
        
        st = current.session_data.session_type
        sp = current.session_data.session_phase
        
        for name, event in self._events.items():
            if not event.is_applicable(st, sp):
                continue
            
            failures = self._faulting_events.get(name, 0)
            if self._session_has_failing_event and failures >= self.MAX_FAILURES_BEFORE_DISABLE:
                continue
            
            try:
                # Execute with timeout via executor (avoids blocking event loop)
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, event.trigger_internal, previous, current
                    ),
                    timeout=self.EVENT_TIMEOUT
                )
                if name in self._faulting_events:
                    self._faulting_events[name] = 0
                    
            except asyncio.TimeoutError:
                failures = self._faulting_events.get(name, 0) + 1
                self._faulting_events[name] = failures
                logger.error(f"TIMEOUT: {name} ({failures}/{self.MAX_FAILURES_BEFORE_DISABLE})")
                if failures >= self.MAX_FAILURES_BEFORE_DISABLE:
                    self._session_has_failing_event = True
                    logger.warning(f"DISABLED: {name}")
                    
            except Exception as e:
                failures = self._faulting_events.get(name, 0) + 1
                self._faulting_events[name] = failures
                logger.error(f"FAIL: {name} ({failures}/{self.MAX_FAILURES_BEFORE_DISABLE}): {e}")
                if failures >= self.MAX_FAILURES_BEFORE_DISABLE:
                    self._session_has_failing_event = True
    
    def get_event(self, name: str) -> Optional[AbstractEvent]:
        return self._events.get(name)
```

---

## 🔴 28 KNOWN BUG FIXES — Integrated list

### FIX-ORIENTATION (Task 0.1) — Use LMUOrientation struct, handle NaN

**Bug:** Original used `c_float * 9`. LMU stores orientation as `rF2Vec3[3]`.

```python
# backend/src/services/lmu_reader.py

class LMUVec3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float)]

class LMUOrientation(ctypes.Structure):
    """3x3 rotation matrix. Row order: X(right), Y(up), Z(forward)."""
    _fields_ = [
        ("row_x", LMUVec3),
        ("row_y", LMUVec3),
        ("row_z", LMUVec3),
    ]

def calculate_rotation(orientation) -> dict:
    """
    CrewChief: RF2GameStateMapper.GetRotation()
    Yaw = atan2(row_z.x, row_z.z)  — heading
    Pitch = atan2(-row_y.z, sqrt(row_x.z² + row_z.z²)) — nose up/down
    Roll = atan2(row_y.x, sqrt(row_x.x² + row_z.x²)) — lateral tilt
    """
    rx, ry, rz = orientation["row_x"], orientation["row_y"], orientation["row_z"]
    yaw = math.atan2(rz["x"], rz["z"])
    pitch = math.atan2(-ry["z"], math.sqrt(rx["z"]**2 + rz["z"]**2))
    roll = math.atan2(ry["x"], math.sqrt(rx["x"]**2 + rz["x"]**2))
    
    # FIX: Handle NaN/Inf from corrupt shared memory
    if math.isnan(yaw) or math.isinf(yaw):
        yaw, pitch, roll = 0.0, 0.0, 0.0
    
    return {"yaw": yaw, "pitch": pitch, "roll": roll}
```

### FIX-BATTERY (Task BatteryEvent) — Normalize percentage

```python
def get_battery_percentage(battery_left: float, battery_capacity: float) -> float:
    """CrewChief: Battery.cs — normalizes fraction or raw percentage to 0-100."""
    if battery_capacity > 0 and battery_left <= 1.0:
        return (battery_left * 100.0) / battery_capacity
    elif battery_left <= 1.0:
        return battery_left * 100.0
    return battery_left
```

### FIX-GAP-SAMPLE (Task PositionEvent) — Sample gaps at 1Hz not 10Hz

```python
# In __init__:
self._gap_sample_counter = 0

# In _check_for_new_overtakes() before gap accumulation:
self._gap_sample_counter += 1
if self._gap_sample_counter % 10 == 0:  # 1Hz at 10Hz loop
    if current.session_data.time_delta_front > 0:
        self._gaps_ahead.append(current.session_data.time_delta_front)
    if current.session_data.time_delta_behind > 0:
        self._gaps_behind.append(current.session_data.time_delta_behind)
```

### FIX-ANTI-BOUNCE (Task PositionEvent) — 1s position change delay

```python
self._pending_position_changes: Dict = {}
self._position_change_lag = 1.0  # seconds

def _filtered_position(self, name: str, old: int, new: int, now: float) -> int:
    """CrewChief: GameStateMapper.getRacePosition() — 1s settling delay."""
    if old == new:
        self._pending_position_changes.pop(name, None)
        return old
    p = self._pending_position_changes.get(name)
    if p and p["new"] == new:
        return new if now >= p["settle"] else old
    self._pending_position_changes[name] = {"new": new, "settle": now + self._position_change_lag}
    return old
```

### FIX-JUST-GONE-GREEN (Task GameStateBuilder) — MUST set timestamp

```python
def _populate_derived_data(gsd, changes, previous_gsd=None):
    """CRITICAL: Must set just_gone_green_time for Position race start messages."""
    sd = gsd.session_data
    if (sd.session_phase == SessionPhase.GREEN and
        previous_gsd and previous_gsd.session_data.session_phase != SessionPhase.GREEN):
        sd.just_gone_green = True
        sd.just_gone_green_time = gsd.now  # FIX: This MUST be set
    else:
        sd.just_gone_green = False
    
    # Track start position
    if sd.just_gone_green or sd.is_new_session:
        if sd.session_start_class_position == 0:
            sd.session_start_class_position = sd.class_position
```

### FIX-OOPPONENT-BEHIND (Task GameStateData) — Missing method

```python
def get_opponent_key_in_front(self, car_class=None):
    """...existing code..."""

def get_opponent_key_behind(self, car_class=None):
    """CrewChief: GameStateData.getOpponentKeyBehind()"""
    closest = None; closest_dist = float('inf')
    pd = self.position_and_motion_data.distance_round_track
    for key, opp in self.opponent_data.items():
        if opp.speed < 0.5 or opp.is_entering_pits: continue
        if car_class and opp.vehicle_class != car_class: continue
        if opp.distance_round_track < pd:
            d = pd - opp.distance_round_track
            if d < closest_dist: closest, closest_dist = key, d
    # Fallback: lapped traffic ahead
    if not closest:
        for key, opp in self.opponent_data.items():
            if opp.speed >= 0.5: return key
    return closest
```

### FIX-AUDIO-BLOCKING (Task AudioPlayer) — Use executor for blocking playback

```python
class AudioPlayer:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audio")
    
    async def process_queues_async(self, now=None, current_gsd=None):
        """Run blocking playback in executor thread to avoid event loop stall."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.process_queues, now, current_gsd)
    
    def process_queues(self, now=None, current_gsd=None):
        """Synchronous. Does NOT call time.sleep() — pauses are no-ops here."""
        now = now or time.time()
        
        # Check pause
        if self.regular_queue_paused:
            if now < self._pause_until:
                return False
            self.regular_queue_paused = False
        
        # Process immediate queue first
        msg = self._get_next_valid(self.immediate_clips, now, current_gsd)
        if msg: self._play_and_log(msg); return True
        
        msg = self._get_next_valid(self.queued_clips, now, current_gsd)
        if msg: self._play_and_log(msg); return True
        return False
    
    def _get_next_valid(self, queue, now, gsd):
        """Find valid message, checking expiry and isMessageStillValid()."""
        for key, msg in list(queue.items()):
            if not msg.is_due(now): continue
            if msg.is_expired(now): queue.pop(key, None); continue
            if not msg.can_be_played: queue.pop(key, None); continue
            # FIX: Pass GSD to isMessageStillValid
            if msg.abstract_event and gsd and not self._is_valid(msg, gsd):
                queue.pop(key, None); continue
            queue.pop(key, None)
            return msg
        return None
    
    def _is_valid(self, msg, gsd):
        return msg.abstract_event.is_message_still_valid(msg.message_name, gsd, msg.validation_data)
    
    def _play_and_log(self, msg):
        self._play_sound(msg)
        self.last_message_played = msg
```

### FIX-FLAGS-FCY (Task FlagsMonitor) — Pause normal queue during FCY

```python
class FlagsMonitorEvent(AbstractEvent):
    def __init__(self, audio_player=None):
        super().__init__(audio_player)
        self._was_fcy = False
    
    def trigger_internal(self, previous, current):
        # FCY entrance: pause normal queue
        if current.flag_data.is_full_course_yellow and not self._was_fcy:
            self._was_fcy = True
            if self.audio_player:
                self.audio_player.pause_queue(30)
                self.audio_player.play_message_immediately(
                    QueuedMessage("flags/full_course_yellow", 0, priority=15)
                )
        # FCY exit: resume
        elif not current.flag_data.is_full_course_yellow and self._was_fcy:
            self._was_fcy = False
            if self.audio_player:
                self.audio_player.unpause_queue()
```

### FIX-MIGRATION (Migration) — Old triggers must be ALERT_ONLY

Before the new event system runs, change ALL 11 old triggers from `LLM_REQUIRED` to `DETERMINISTIC_ONLY`:

```python
# In triggers.py — ALL 11 triggers change TriggerAction:
class FuelCriticalTrigger(BaseTrigger):
    def __init__(self):
        super().__init__(..., TriggerAction.DETERMINISTIC_ONLY, ...)
class SafetyCarTrigger(BaseTrigger):
    def __init__(self):
        super().__init__(..., TriggerAction.DETERMINISTIC_ONLY, ...)
# ... same for all 11 LLM_REQUIRED triggers
```

### FIX-DEEPCOPY (Performance) — No deepcopy; build directly

```python
# Instead of deepcopy(flat_dict), build GSD directly and discard the raw dict:
gsd = build_game_state_data(flat, previous_gsd)
# flat is GC'd immediately — no extra copy
```

### FIX-SPOTTER-STILL-THERE (Spotter) — Clear pending on all-clear

```python
def trigger(self, player_state, opponents, now):
    # ... existing logic ...
    if self.cars_on_left == 0 and self.cars_on_right == 0:
        if self.cars_on_left_previous > 0 or self.cars_on_right_previous > 0:
            self._next_message_type = "clear_all_round"  # FIX: covers single-side too
            self._next_message_due = now + self.clear_message_delay
            # FIX: Reset all reporting flags
            self._reported_single_overlap_left = False
            self._reported_single_overlap_right = False
            self._reported_double_overlap_left = False
            self._reported_double_overlap_right = False
```

### FIX-DAMAGE-LAST-IMPACT (DamageReporting) — Reset between sessions

```python
class DamageReportingEvent(AbstractEvent):
    def clear_state(self):
        # FIX: Reset impact time AND all cached damage levels
        self._last_impact_time = -1.0
        self._component_destroyed = None
        self._reported_damage_levels.clear()
        # ... rest of clear_state ...
```

---

## 🔴 BASE_EVENT — CORRECTED (formation suppression, class filtering)

**File:** `backend/src/intelligence/base_event.py`

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from backend.models.enums import SessionType, SessionPhase
from backend.models.game_state_data import GameStateData
from backend.models.messages import QueuedMessage, MessageFragment, message_contents, Pause, DelayedMessageEvent
from backend.intelligence.event_flags import event_flags

class AbstractEvent(ABC):
    """Base class for ALL events. Each event overrides trigger_internal()."""
    
    applicable_session_types: List[SessionType] = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.PRIVATE_QUALIFY,
        SessionType.RACE, SessionType.HOT_LAP, SessionType.LONE_PRACTICE
    ]
    applicable_session_phases: List[SessionPhase] = [
        SessionPhase.GREEN, SessionPhase.COUNTDOWN
    ]
    
    # Message category for per-car-class filtering. Override in each event.
    # CrewChief: carClassData.json enabledMessageTypes
    message_category: str = "ALL"
    
    # Event sequence (for ordering within same tick, lower = first)
    sequence: int = 100
    
    def __init__(self, audio_player=None):
        self.audio_player = audio_player
        self._use_fahrenheit = False
        self._use_psi = False
    
    @abstractmethod
    def trigger_internal(self, previous: Optional[GameStateData], current: GameStateData):
        """Main logic. Called by EventEngine every tick."""
        pass
    
    @abstractmethod
    def clear_state(self):
        """Reset event state between sessions."""
        pass
    
    def is_applicable(self, session_type: SessionType, session_phase: SessionPhase) -> bool:
        return (session_type in self.applicable_session_types and
                session_phase in self.applicable_session_phases)
    
    def should_suppress(self, gsd: GameStateData) -> bool:
        """FIX: Check formation lap suppression AND car class message type filtering.
        
        CrewChief suppresses most events during formation lap.
        Also filters by car class enabledMessageTypes.
        """
        if event_flags.on_manual_formation_lap:
            return True
        if not self._is_enabled_for_class(gsd):
            return True
        return False
    
    def _is_enabled_for_class(self, gsd: GameStateData) -> bool:
        """FIX: Per-car-class message filtering.
        
        CrewChief: carClassData.json enabledMessageTypes per class.
        GT3 → "ALL", ROAD_B → "TYRE_TEMPS, FUEL, LOCKING_AND_SPINNING"
        """
        from backend.data.car_class_data import get_car_class_by_name
        cc = get_car_class_by_name(gsd.car_class)
        enabled = cc.enabled_message_types
        if "ALL" in enabled:
            return True
        if "NONE" in enabled:
            return False
        return self.message_category in enabled
    
    def is_message_still_valid(self, event_subtype: str, current: GameStateData,
                                validation_data: Optional[Dict] = None) -> bool:
        return current is not None and self.is_applicable(
            current.session_data.session_type, current.session_data.session_phase
        )
    
    def respond(self, voice_message: str):
        pass
    
    def convert_temp(self, temp_celsius: float, precision: int = 1) -> int:
        if self._use_fahrenheit:
            return int(round((temp_celsius * 9.0 / 5.0) + 32.0))
        return int(round(temp_celsius / precision) * precision)
    
    def convert_pressure(self, pressure_kpa: float, dp: int = 1) -> float:
        if self._use_psi:
            return round(pressure_kpa / 6.894, dp)
        return round(pressure_kpa / 100.0, 2)
    
    @staticmethod
    def message_contents(*objects) -> List[MessageFragment]:
        return message_contents(*objects)
    
    @staticmethod
    def Pause(ms: int) -> MessageFragment:
        return Pause(ms)


class FakeAudioPlayer:
    """Test double for unit tests."""
    def __init__(self):
        self.messages: List[QueuedMessage] = []
        self.immediate_messages: List[QueuedMessage] = []
    def play_message(self, msg, **kw): self.messages.append(msg)
    def play_message_immediately(self, msg, **kw): self.immediate_messages.append(msg)
    def play_spotter_message(self, path, **kw): pass
    def pause_queue(self, s): pass
    def unpause_queue(self): pass
    def purge_queues(self, **kw): pass
    def process_queues(self, **kw): pass
    def clear(self):
        self.messages.clear(); self.immediate_messages.clear()
```

---

## 🔴 EVENT FLAGS — CORRECTED (asyncio-safe)

**File:** `backend/src/intelligence/event_flags.py`

```python
import asyncio
from dataclasses import dataclass, field
from typing import Set, Optional


@dataclass
class EventFlags:
    """Cross-event shared state. All access via async set/get to avoid races."""
    
    # Pit stop flags
    is_pitting_this_lap: bool = False
    played_request_pit_on_this_lap: bool = False
    played_pit_request_cancelled_on_this_lap: bool = False
    waiting_for_mandatory_stop_timer: bool = False
    
    # Lap counter
    white_flag_last_lap_announced: bool = False
    played_pre_lights_message: bool = False
    pre_start_temps_announced: bool = False
    
    # Strategy (shared with Opponents, WatchedOpponents)
    opponents_who_will_exit_close_in_front: Set[str] = field(default_factory=set)
    opponents_who_will_exit_close_behind: Set[str] = field(default_factory=set)
    opponent_front_to_watch_for_pitting: Optional[str] = None
    opponent_behind_to_watch_for_pitting: Optional[str] = None
    play_pit_position_estimates: bool = False
    pit_stall_is_blocked: bool = False
    
    # Damage
    waiting_for_driver_is_ok_response: bool = False
    
    # Formation
    on_manual_formation_lap: bool = False
    
    # Async lock
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
    async def set(self, name: str, value: bool):
        async with self._lock:
            setattr(self, name, value)
    
    async def get(self, name: str) -> bool:
        async with self._lock:
            return getattr(self, name, False)
    
    def reset_all(self):
        """Must be called from main loop only (no race)."""
        for fn in self.__dataclass_fields__:
            if fn.startswith('_'): continue
            ft = self.__dataclass_fields__[fn].type
            if ft == bool: setattr(self, fn, False)
            elif 'set' in str(ft): setattr(self, fn, set())
            elif 'Optional' in str(ft): setattr(self, fn, None)


event_flags = EventFlags()
```

---

## 📋 IMPLEMENTATION ORDER (58 tasks, ~69 days)

### Phase 0 — Foundations (8 tasks, 5 days)
1. FrameCache with dedup + reinit
2. LMUReader with correct LMUOrientation struct
3. SessionRunningTime (mCurrentET)
4. Opponent fields (50+ per rival)
5. DeltaTime with lap differences
6. StateDiff with anti-bounce
7. TrackDefinition + CarClass data
8. WebSocket connection fix

### Phase 1 — Data Model (6 tasks, 5 days)
1. All enums
2. GameStateData (30+ dataclasses)
3. GameStateBuilder + _populate_derived_data (with just_gone_green_time)
4. QueuedMessage + MessageFragment + DelayedMessageEvent
5. EventFlags (asyncio-safe)
6. AbstractEvent (with formation suppression, class filtering)

### Phase 2 — Cartesian Spotter (4 tasks, 5 days)
1. Orientation utilities (with NaN check)
2. Core algorithm with still_there fix
3. Grid side detection
4. Integration with main loop

### Phase 3 — Event Engine (4 tasks, 3 days)
1. Engine with async timeout
2. Fault tolerance (10 failures → disable)
3. Migration from old triggers (ALL → DETERMINISTIC_ONLY)
4. GlobalBehaviourSettings + Utilities

### Phase 4 — Audio System (7 tasks, 7 days)
1. SoundCache (available_sounds, variety, beeps)
2. AudioPlayer (dual queue, priority, executor thread)
3. Queue validation (isMessageStillValid with GSD)
4. Queue pause (FCY)
5. NumberReader + ColloquialTime
6. PlaybackModerator
7. Personalisation (prefix/suffix)

### Phase 5-7 — All 29 Events (23 tasks, 34 days)
Implement in ORDER (each needs previous):
1. LapCounter (pre-lights, green, last lap)
2. Position (overtakes, race start, reminders)
3. PitStops (countdown, limiter, mandatory stops)
4. Fuel (consumption, windows, FCY)
5. Battery (LMU WEC VE)
6. TyreMonitor (14 compounds, 4 brake types)
7. FlagsMonitor (7 FCY phases)
8. DamageReporting (5 components, 5 levels)
9. EngineMonitor (60s window)
10. Opponents (leader, retirement, tyre changes)
11. LapTimes (sector deltas, consistency)
12. RaceTime (20/15/10/5/2/0 minutes)
13. Timings (gap status, attack/defend)
14. PushNow (strategic push)
15. Strategy (post-pit prediction)
16. Penalties (4 cut track levels, 10+ causes)
17. DriverSwaps (LMU WEC stints)
18. OvertakingAids (DRS, PtP)
19. MulticlassWarnings (zones by track length)
20. WatchedOpponents (team mate, rival)
21. SessionEndMessages (win/podium/last/rant)
22. CommonActions (orchestrator)
23. AlarmClock

### Phase 8 — Voice & Config (4 tasks, 5 days)
1. SpeechRecogniser (70+ commands)
2. UserSettings (200+ settings, profiles)
3. WebSocket message format (MessagePack)
4. Frontend AudioQueue update

### Phase 9 — Integration Tests (4 tasks, 5 days)
1. Full pipeline trace replay
2. Spotter with real opponent data
3. Fault tolerance verification
4. All 29 events cross-event dependency test

---

## ✅ FINAL VERIFICATION CHECKLIST

**Before marking ANY event as complete:**
- [ ] 5+ unit tests passing (TDD: red→green→refactor)
- [ ] `should_suppress()` returns correct value for formation + car class
- [ ] `is_message_still_valid()` handles stale messages correctly
- [ ] `clear_state()` resets ALL state variables (including cached damage, last_impact_time, etc.)
- [ ] Cooldowns use `SessionRunningTime` (not `SessionTimeRemaining`)
- [ ] Audio messages use `message_contents()` with proper folder paths
- [ ] Event registered in `EventEngine`
- [ ] Cross-event flags set via `event_flags` (not direct static access)
- [ ] NaN-safe math on all orientation/position calculations
- [ ] 1Hz sampling where CrewChief uses 1s intervals (gaps, fuel windows)

**Integration test must pass:**
- [ ] Full pipeline: FrameCache → GameStateBuilder → EventEngine → AudioPlayer
- [ ] All 29 events produce correct messages during simulated race
- [ ] Spotter detects car left/right with real coordinate data
- [ ] Fault tolerance: slow event times out after 2s, disables after 10
- [ ] Frame dedup: same frame repeated produces same GSD (no phantom overtakes)
- [ ] Shared memory recovery: game restart handled without crash
- [ ] All 20 FIX-* items verified applied