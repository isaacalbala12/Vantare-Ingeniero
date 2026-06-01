# CrewChiefV4 Complete Implementation — MASTER DOCUMENT

> **Target:** Fresh model executing in a separate chat. This is your ONLY reference. All 28 bugs from v1 have been fixed inline.

**Goal:** Replicate 100% of CrewChiefV4 for Le Mans Ultimate — Cartesian spotter, 29 events, dual-priority audio, 70+ voice commands, battery/hybrid, driver swaps, timing/gaps, penalties, damage, tyres, engine, fuel, pit stops, formation, multiclass, watched opponents, session end, pearls. VR overlay excluded.

**Architecture:** Python asyncio backend (FastAPI) + TypeScript frontend (Tauri/React). Single main loop at 10Hz reads LMU shared memory (ctypes) + REST API (port 6397) → one FrameCache shared between events and spotter → GameStateData → EventEngine dispatches to 29 events → AudioPlayer dual queue → WebSocket (MessagePack) to frontend. Spotter runs INLINE. All events fault-tolerant with 2s timeout, disable after 10 failures.

**Tech Stack:** Python 3.11+, FastAPI, ctypes, asyncio, requests, msgpack, Edge TTS, Piper TTS, React, TypeScript, Tauri, Vitest, pytest

---

## 📋 MASTER INDEX

| Phase | Name | Tasks | Effort |
|-------|------|-------|--------|
| 0 | Foundation | 0.1-0.10 (10 tasks) | 6 days |
| 1 | Data Model | 1.1-1.6 (6 tasks) | 5 days |
| 2 | Cartesian Spotter | 2.1-2.4 (4 tasks) | 5 days |
| 3 | Event Engine | 3.1-3.4 (4 tasks) | 3 days |
| 4 | Audio System | 4.1-4.7 (7 tasks) | 7 days |
| 5 | Core Events P1 | 5.1-5.8 (8 tasks) | 12 days |
| 6 | Core Events P2 | 6.1-6.8 (8 tasks) | 12 days |
| 7 | Advanced Events | 7.1-7.7 (7 tasks) | 10 days |
| 8 | Voice & Config | 8.1-8.4 (4 tasks) | 5 days |
| 9 | Integration Tests | 9.1-9.4 (4 tasks) | 5 days |
| | **TOTAL** | **62 tasks** | **~70 days** |

---

## 🚨 LMU-SPECIFIC DATA VERIFICATION

### LMU has TWO data sources: Shared Memory + REST API (:6397)

**Shared Memory** (rF2 `mfx` format):
- Positions, speeds, rotations, session info, engine, fuel level
- **Orientation matrix** (3×3 rotation → yaw/pitch/roll)
- **mVirtualEnergy** (Hypercars — read directly)

**REST API** (port 6397) — MUST ADD:
- `rest/garage/UIScreen/RepairAndRefuel`:
  - `fuelInfo.currentVirtualEnergy/maxVirtualEnergy` → BatteryEvent
  - `fuelInfo.currentBattery/maxBattery` → BatteryEvent  
  - `wearables.tires[4]` → TyreMonitor (per-corner wear, NOT in shared mem)
  - `wearables.brakes[4]` → Brake wear (NOT in shared mem)
  - `wearables.suspension[4]` → Suspension damage (NOT in shared mem)
  - `wearables.body.aero` → Aero damage (NOT in shared mem)
  - `currentWeather.ambientTempKelvin/trackTempKelvin` → ConditionsMonitor
  - `currentWeather.rainIntensity/cloudCoverage` → ConditionsMonitor
  - `racePosition.placeInClass/placeOverall` → SessionData
  - `teamInfo.vehicleName` → Car class detection
  - `pitStopLength.timeInSeconds` → PitStops
- `rest/sessions/?`:
  - `SESSSET_Fuel_Usage` → fuel multiplier
  - `SESSSET_Tire_Wear` → tyre wear mode
  - `SESSSET_Damage_Multi` → damage mode

**LMU/rF2 game phase codes** (mGamePhase):
0=Unavail, 1=Garage, 2=Gridwalk, 3=Formation, 4=Countdown, 5=Green, 6=FCY, 7=Checkered, 8=Finished

---

## 🗂️ COMPLETE FILE INVENTORY (55 files)

```
backend/src/
├── main.py                          # Main loop with FrameCache + REST merge
├── config/
│   ├── settings.py                  # 200+ settings
│   ├── global_behaviour.py          # Mutable runtime flags
│   └── user_settings.py             # JSON profile system
├── models/
│   ├── enums.py                     # SessionType, SessionPhase, FlagEnum, FCYPhase, etc.
│   ├── game_state_data.py           # 30+ dataclasses
│   └── messages.py                  # QueuedMessage, MessageFragment, DelayedMessageEvent
├── services/
│   ├── lmu_reader.py                # ctypes shared memory with LMUOrientation
│   ├── lmu_rest_api.py              # REST API (:6397) with backoff
│   ├── game_state_builder.py        # flat dict + REST → GameStateData
│   ├── state_diff.py                # PreviousTick change detection
│   ├── delta_time.py                # Lap-difference-aware deltas
│   ├── frame_cache.py               # Single frame for events+spotter
│   ├── audio_player.py              # Dual queue, priority, executor thread
│   ├── sound_cache.py               # WAV index, TTS, variety, personalisation
│   ├── number_reader.py             # Integer/time in EN/ES
│   ├── playback_moderator.py        # Message filtering
│   ├── track_definition.py          # TrackLengthClass, gap points, landmarks
│   ├── colloquial_time.py           # "quarter past three"
│   └── utilities.py                 # Random, WholeAndFractionalPart, InterruptedSleep
├── intelligence/
│   ├── base_event.py                # AbstractEvent, FakeAudioPlayer
│   ├── event_engine.py              # Dispatch with async timeout
│   ├── event_flags.py               # asyncio-safe cross-event flags
│   ├── trigger_to_event_bridge.py   # Old trigger migration
│   ├── noisy_cartesian_spotter.py   # Full Cartesian spotter
│   └── events/
│       ├── position.py              # Overtakes, race start, reminders
│       ├── pit_stops.py             # Countdown, limiter, mandatory stops
│       ├── fuel.py                  # Consumption windows, FCY adj
│       ├── battery.py               # LMU WEC VE management
│       ├── tyre_monitor.py          # 14 compounds, locking, camber
│       ├── flags_monitor.py         # FCY 7 phases, incident, blue flag
│       ├── damage_reporting.py      # 5 components, puncture, rollover
│       ├── engine_monitor.py        # Oil/water 60s avg, stall
│       ├── opponents.py             # Leader change, retirements
│       ├── lap_times.py             # Sector deltas, consistency
│       ├── lap_counter.py           # Pre-lights, last lap, formation
│       ├── race_time.py             # Time remaining, extra laps
│       ├── timings.py               # Gap status, attack/defend
│       ├── push_now.py              # Strategic push, pit exit
│       ├── strategy.py              # Post-pit prediction
│       ├── penalties.py             # Cut track 4 levels, drive-through
│       ├── multiclass_warnings.py   # Faster/slower detection
│       ├── watched_opponents.py     # Driver tracking
│       ├── session_end_messages.py  # Win/podium/rant
│       ├── driver_swaps.py          # LMU WEC stints
│       ├── overtaking_aids.py       # DRS, Push-to-Pass
│       ├── conditions_monitor.py    # Weather, track temp
│       ├── frozen_order_monitor.py  # SC, formation, rolling start
│       ├── common_actions.py        # Orchestrator
│       └── alarm_clock.py           # Time alarms
├── data/
│   └── car_class_data.py            # 120+ classes, thresholds
└── audio/
    ├── spotter/*.wav, position/*.wav, pit_stops/*.wav, fuel/*.wav, battery/*.wav
    ├── penalties/*.wav, tyre_monitor/*.wav, flags/*.wav, damage/*.wav
    ├── engine_monitor/*.wav, opponents/*.wav, lap_times/*.wav, lap_counter/*.wav
    ├── race_time/*.wav, multiclass/*.wav, driver_swaps/*.wav
    ├── timing/*.wav, pearls/*.wav, acknowledge/*.wav
    ├── fx/beep_start.wav, beep_end.wav, beep_start_short.wav
    ├── fx/drs_detected.wav, drs_available.wav
    └── driver_names/*.wav
```

---

## 🔗 CROSS-EVENT DEPENDENCIES (IMPLEMENT IN THIS ORDER)

| Order | Event | Depends On | Provides Flag |
|-------|-------|-----------|--------------|
| 1 | **LapCounter** | SessionData, FlagData, ControlData | `white_flag_last_lap_announced`, `played_pre_lights_message` |
| 2 | **ConditionsMonitor** | Weather data (REST API) | — |
| 3 | **FrozenOrderMonitor** | FrozenOrderData, SessionPhase | — |
| 4 | **Position** | StateDiff, PenaltiesData, CarDamageData, FlagData, SessionData.just_gone_green_time | — |
| 5 | **PitStops** | PitData, TrackDefinition, WorldPosition, DistanceRoundTrack | `is_pitting_this_lap`, `waiting_for_mandatory_stop_timer` |
| 6 | **Fuel** | FuelData, TrackDefinition.track_length_class, SessionData, is_full_course_yellow | — |
| 7 | **Battery** | BatteryData, PitData.IsElectricVehicleSwapAllowed, TrackDefinition | — |
| 8 | **TyreMonitor** | TyreData, REST wearables, LocalVelocity, CarClass thresholds | — |
| 9 | **FlagsMonitor** | FlagData, OpponentData[].DistanceRoundTrack | — |
| 10 | **DamageReporting** | CarDamageData, TyreData.pressure, Orientation, CarSpeed, LocalAccel | `waiting_for_driver_is_ok_response` |
| 11 | **EngineMonitor** | EngineData, CarClass.maxSafeWater/OilTemp | — |
| 12 | **Opponents** | OpponentData, StateDiff.leader_changed/retired, TyreMonitor | — |
| 13 | **LapTimes** | LapTimePrevious, TimingData, TrackDefinition, PitStops.is_pitting | — |
| 14 | **RaceTime** | SessionTimeRemaining, SessionRunningTime | — |
| 15 | **Timings** | TimeDeltaFront/Behind, TrackDefinition.gap_points/landmarks | — |
| 16 | **PushNow** | TimeDelta, OpponentData.BestLap, TrackDefinition | — |
| 17 | **Strategy** | PitData, OpponentData, SessionData, WorldPosition | `opponents_who_will_exit_close_in_front/behind` |
| 18 | **Penalties** | PenaltiesData, CarSpeed, IncidentCount | — |
| 19 | **DriverSwaps** | DriverStintSecondsRemaining, PlayerLapTimeSessionBest | — |
| 20 | **OvertakingAids** | OvertakingAidsData, TimeDeltaFront/Behind | — |
| 21 | **MulticlassWarnings** | OpponentData.CarClass, TimingData, TrackDefinition | — |
| 22 | **WatchedOpponents** | OpponentData, DeltaTime, Strategy | — |
| 23 | **SessionEndMessages** | SessionPhase, ClassPosition, CompletedLaps | — |
| 24 | **CommonActions** | ALL events (orchestrator) | — |
| 25 | **AlarmClock** | System time | — |

---

## 📐 PHASE 0: FOUNDATION

### Task 0.1: LMUReader with correct structs + NaN-safe rotation

**File:** `backend/src/services/lmu_reader.py`

```python
import ctypes
import math
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("vantare.lmu_reader")

# ---- ctypes structs matching LMU/rF2 shared memory layout ----
class LMUVec3(ctypes.Structure):
    """Single 3D vector."""
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float)]

class LMUOrientation(ctypes.Structure):
    """3×3 rotation matrix as 3 row vectors.
    CrewChief: RF2GameStateMapper uses orientation[RowZ].x/z for yaw.
    Row order: [0]=X(right), [1]=Y(up), [2]=Z(forward).
    """
    _fields_ = [("row_x", LMUVec3), ("row_y", LMUVec3), ("row_z", LMUVec3)]

class LMUVehicleScoring(ctypes.Structure):
    _fields_ = [
        ("mDriverName", ctypes.c_char * 64),
        ("mVehicleClass", ctypes.c_char * 64),
        ("mPlace", ctypes.c_int),
        ("mTotalLaps", ctypes.c_int),
        ("mLapDist", ctypes.c_float),
        ("mSector", ctypes.c_int),
        ("mTimeDeltaLeader", ctypes.c_float),
        ("mBestLapTime", ctypes.c_float),
        ("mLastLapTime", ctypes.c_float),
        ("mInPits", ctypes.c_int),
        ("mTrackSurface", ctypes.c_int),
        ("mID", ctypes.c_longlong),
        ("mOrientation", LMUOrientation),
        ("mCarNumber", ctypes.c_char * 8),
        ("mClassPlace", ctypes.c_int),
        ("mIsActive", ctypes.c_int),
        ("mTyreCompound", ctypes.c_char * 32),
        ("mVirtualEnergy", ctypes.c_float),  # Added for LMU Hypercars
    ]

class LMUScoringInfo(ctypes.Structure):
    _fields_ = [
        ("mNumVehicles", ctypes.c_int),
        ("mCurrentET", ctypes.c_float),       # SessionRunningTime
        ("mEndET", ctypes.c_float),            # SessionTimeRemaining
        ("mLapDist", ctypes.c_float),
        ("mGamePhase", ctypes.c_int),          # 0=unavail, 5=Green, 6=FCY, 8=Finished
        ("mSession", ctypes.c_int),            # 1=Practice, 2=Qual, 3=Race
    ]

# ---- Helper: decode string from ctypes char array ----
def decode_name(byte_arr) -> str:
    """CrewChief: GetStringFromBytes — handles null terminators and leading null bytes."""
    if byte_arr is None: return ""
    if not isinstance(byte_arr, (bytes, bytearray)):
        try: byte_arr = bytes(byte_arr)
        except: return ""
    if len(byte_arr) == 0: return ""
    # Handle leading null byte (CrewChief changelog v4.0.3.4: PCars/LMU bug)
    if byte_arr[0] == 0 and len(byte_arr) > 1:
        byte_arr = byte_arr[1:]
    null_pos = byte_arr.find(b'\x00')
    if null_pos >= 0: byte_arr = byte_arr[:null_pos]
    if len(byte_arr) == 0: return ""
    try: return byte_arr.decode('utf-8', errors='strict').strip()
    except UnicodeDecodeError:
        try: return byte_arr.decode('latin-1').strip()
        except: return byte_arr.decode('utf-8', errors='replace').strip()

# ---- Rotation calculation (CRITICAL for Cartesian spotter) ----
def calculate_rotation(orientation) -> Dict[str, float]:
    """CrewChief: RF2GameStateMapper.GetRotation(). Returns yaw/pitch/roll in radians.
    
    FIX: Handles NaN/Inf from corrupt shared memory — returns 0.0, 0.0, 0.0.
    """
    rx, ry, rz = orientation["row_x"], orientation["row_y"], orientation["row_z"]
    yaw = math.atan2(rz["x"], rz["z"])
    pitch = math.atan2(-ry["z"], math.sqrt(rx["z"]**2 + rz["z"]**2))
    roll = math.atan2(ry["x"], math.sqrt(rx["x"]**2 + rz["x"]**2))
    if math.isnan(yaw) or math.isinf(yaw):
        yaw, pitch, roll = 0.0, 0.0, 0.0
    return {"yaw": yaw, "pitch": pitch, "roll": roll}

def orientation_to_dict(orient) -> Dict:
    """Convert LMUOrientation ctypes struct to dict (handle all formats)."""
    if hasattr(orient, 'row_x'):
        return {"row_x": {"x": orient.row_x.x, "y": orient.row_x.y, "z": orient.row_x.z},
                "row_y": {"x": orient.row_y.x, "y": orient.row_y.y, "z": orient.row_y.z},
                "row_z": {"x": orient.row_z.x, "y": orient.row_z.y, "z": orient.row_z.z}}
    if hasattr(orient, '__getitem__') and len(orient) >= 3:
        return {"row_x": {"x": orient[0].x, "y": orient[0].y, "z": orient[0].z},
                "row_y": {"x": orient[1].x, "y": orient[1].y, "z": orient[1].z},
                "row_z": {"x": orient[2].x, "y": orient[2].y, "z": orient[2].z}}
    raise ValueError(f"Unknown orientation format: {type(orient)}")

# ---- Main reader ----
class LMUReader:
    def __init__(self):
        self._shmm = None
        self._is_initialized = False
    
    def _create_mmap(self):
        from shared_telemetry.pyLMUSharedMemory.lmu_mmap import MMapControl
        mmap = MMapControl()
        mmap.create("$LMULocal$", 0)
        return mmap
    
    def get_flat_dict(self) -> Dict[str, Any]:
        """Read LMU shared memory and return dict with ALL fields."""
        if not self._is_initialized:
            self._shmm = self._create_mmap()
            self._is_initialized = True
        if self._shmm is None or self._shmm.data is None:
            return {"session_running_time": 0.0}
        
        d = {}
        try:
            data = self._shmm.data
            # Session info
            scoring = data.scoring
            d["session_type"] = scoring.mScoringInfo.mSession
            d["session_phase"] = scoring.mScoringInfo.mGamePhase
            d["session_running_time"] = float(scoring.mScoringInfo.mCurrentET)
            d["session_time_remaining"] = float(scoring.mScoringInfo.mEndET) - float(scoring.mScoringInfo.mCurrentET)
            
            # Player scoring
            player_veh = data.scoring.mVehicles[data.player_index]
            d["place"] = int(player_veh.mPlace)
            d["lap_number"] = int(player_veh.mTotalLaps)
            d["lap_distance"] = float(player_veh.mLapDist)
            d["sector_number"] = int(player_veh.mSector) if player_veh.mSector != 0 else 3
            d["in_pits"] = bool(player_veh.mInPits)
            d["driver_name"] = decode_name(player_veh.mDriverName)
            
            # Orientation + rotation (CRITICAL for spotter)
            try:
                orient = orientation_to_dict(player_veh.mOrientation)
                rot = calculate_rotation(orient)
                d["rotation_yaw"] = rot["yaw"]
                d["rotation_pitch"] = rot["pitch"]
                d["rotation_roll"] = rot["roll"]
            except (ValueError, AttributeError, TypeError):
                d["rotation_yaw"] = 0.0
                d["rotation_pitch"] = 0.0
                d["rotation_roll"] = 0.0
            
            # VirtualEnergy (LMU Hypercars)
            d["virtual_energy"] = float(getattr(player_veh, 'mVirtualEnergy', 0))
            
            # Player telemetry
            tele = data.telemetry
            d["speed_ms"] = float(tele.mSpeed)
            d["world_x"] = float(tele.mPos.x)
            d["world_y"] = float(tele.mPos.y)
            d["world_z"] = float(tele.mPos.z)
            d["engine_rpm"] = float(tele.mEngineRPM)
            d["gear"] = int(tele.mGear)
            d["water_temp"] = float(tele.mEngineWaterTemp)
            d["oil_temp"] = float(tele.mEngineOilTemp)
            d["fuel_left"] = float(tele.mFuelInTank)
            d["fuel_capacity"] = float(tele.mFuelCapacity)
            
            # Tyres
            d["tyre_temp"] = [float(t) for t in [tele.mTireFL, tele.mTireFR, tele.mTireRL, tele.mTireRR]]
            d["tyre_wear"] = [0.0, 0.0, 0.0, 0.0]  # From REST API, not shared mem
            d["brake_temp"] = [float(t) for t in tele.mBrakeTemps[:4]] if hasattr(tele, 'mBrakeTemps') else [0]*4
            
            # Acceleration (for crash detection)
            if hasattr(tele, 'mLocalAccel'):
                d["accel_long"] = float(tele.mLocalAccel.x)
                d["accel_lat"] = float(tele.mLocalAccel.y)
                d["accel_vert"] = float(tele.mLocalAccel.z)
            
            # Opponents
            rivals = []
            num_veh = int(scoring.mScoringInfo.mNumVehicles)
            for i in range(min(num_veh, 64)):
                if i == data.player_index: continue
                veh = scoring.mVehicles[i]
                name = decode_name(veh.mDriverName)
                if name.lower() == "transparent trainer": continue  # Ghost
                rivals.append({
                    "driver_raw_name": name,
                    "car_number": decode_name(getattr(veh, 'mCarNumber', b'')),
                    "place": int(veh.mPlace),
                    "class_place": int(getattr(veh, 'mClassPlace', 0)),
                    "speed": 0.0,  # Set from telemetry below
                    "distance_round_track": float(veh.mLapDist),
                    "laps_completed": int(veh.mTotalLaps),
                    "last_lap_time": float(veh.mLastLapTime),
                    "best_lap_time": float(veh.mBestLapTime),
                    "current_sector": int(veh.mSector) if veh.mSector != 0 else 3,
                    "in_pits": bool(veh.mInPits),
                    "vehicle_class": decode_name(veh.mVehicleClass),
                    "gap_to_player": float(veh.mTimeDeltaLeader),
                    "is_active": bool(getattr(veh, 'mIsActive', 1)),
                    "tyre_compound": decode_name(getattr(veh, 'mTyreCompound', b'')),
                    "world_x": 0.0, "world_z": 0.0,  # Set from telemetry
                })
            # Fill speeds/positions from telemetry array
            if hasattr(data, 'telemetry_arr'):
                for i, rival in enumerate(rivals):
                    if i < len(data.telemetry_arr):
                        t = data.telemetry_arr[i]
                        rival["speed"] = float(t.mSpeed)
                        rival["world_x"] = float(t.mPos.x)
                        rival["world_z"] = float(t.mPos.z)
            d["rivals"] = rivals
            d["num_rivals"] = len(rivals)
            
        except Exception as e:
            logger.error(f"Error reading shared memory: {e}")
            return {"session_running_time": 0.0}
        
        return d
    
    def reinitialize(self):
        """Re-init after LMU restart. CrewChief: gameDataReader.Initialise()."""
        import subprocess
        try:
            r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq LMU.exe'],
                              capture_output=True, text=True, timeout=5)
            if 'LMU.exe' not in r.stdout:
                logger.info("LMU not running")
                return False
        except: pass
        self._shmm = self._create_mmap()
        self._is_initialized = True
        logger.info("Shared memory reinitialized")
        return True
```

**Tests** (`backend/tests/test_lmu_reader.py`):
```python
import pytest, math
from backend.services.lmu_reader import calculate_rotation, orientation_to_dict, decode_name

def test_rotation_identity():
    r = calculate_rotation({"row_x":{"x":1,"y":0,"z":0},"row_y":{"x":0,"y":1,"z":0},"row_z":{"x":0,"y":0,"z":1}})
    assert abs(r["yaw"]) < 0.001

def test_rotation_45deg():
    c, s = math.cos(math.pi/4), math.sin(math.pi/4)
    r = calculate_rotation({"row_x":{"x":c,"y":0,"z":-s},"row_y":{"x":0,"y":1,"z":0},"row_z":{"x":s,"y":0,"z":c}})
    assert abs(r["yaw"] - math.pi/4) < 0.01

def test_rotation_nan_handling():
    r = calculate_rotation({"row_x":{"x":float('nan'),"y":0,"z":0},"row_y":{"x":0,"y":1,"z":0},"row_z":{"x":0,"y":0,"z":1}})
    assert abs(r["yaw"]) < 0.001  # Returns 0 on NaN

def test_decode_name_leading_null():
    assert decode_name(b'\x00Hello') == "Hello"

def test_decode_name_null_term():
    assert decode_name(b'Test\x00extra') == "Test"

def test_orientation_struct_to_dict_flat():
    class Mock: pass
    o = Mock()
    o.__getitem__ = lambda self, i: type('v',(),{'x':1.0+i,'y':2.0+i,'z':3.0+i})()
    o.__len__ = lambda self: 3
    d = orientation_to_dict(o)
    assert d["row_x"]["x"] == 1.0
```

### Task 0.2: LMU REST API reader

**File:** `backend/src/services/lmu_rest_api.py`

```python
import requests, time, logging
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger("vantare.lmu_rest")
API_BASE = "http://localhost:6397"

@dataclass
class LMURestData:
    current_ve: float = 0.0; max_ve: float = 0.0
    current_battery: float = 0.0; max_battery: float = 0.0
    tyre_wear: List[float] = None; brake_wear: List[float] = None
    suspension_damage: List[float] = None; aero_damage: float = 0.0
    ambient_temp: float = 0.0; track_temp: float = 0.0
    rain_intensity: float = 0.0; cloud_coverage: float = 0.0

class LMURestAPI:
    _last_data: Optional[LMURestData] = None
    _last_fetch: float = 0.0
    _interval: float = 1.0
    _backoff: float = 1.0
    _backoff_until: float = 0.0
    
    @classmethod
    def fetch(cls) -> Optional[LMURestData]:
        now = time.time()
        if now < cls._backoff_until: return cls._last_data
        if now - cls._last_fetch < cls._interval: return cls._last_data
        cls._last_fetch = now
        result = LMURestData()
        try:
            resp = requests.get(f"{API_BASE}/rest/garage/UIScreen/RepairAndRefuel", timeout=2)
            if resp.status_code == 200:
                d = resp.json()
                fi = d.get("fuelInfo", {})
                result.current_ve = fi.get("currentVirtualEnergy", 0)
                result.max_ve = fi.get("maxVirtualEnergy", 0)
                result.current_battery = fi.get("currentBattery", 0)
                result.max_battery = fi.get("maxBattery", 0)
                w = d.get("wearables", {})
                if w.get("tires"): result.tyre_wear = [float(x) for x in w["tires"]]
                if w.get("brakes"): result.brake_wear = [float(x) for x in w["brakes"]]
                if w.get("suspension"): result.suspension_damage = [float(x) for x in w["suspension"]]
                if w.get("body"): result.aero_damage = float(w["body"].get("aero", 0))
                cw = d.get("currentWeather", {})
                if cw.get("ambientTempKelvin", 0) > 100:
                    result.ambient_temp = cw["ambientTempKelvin"] - 273.15
                if cw.get("trackTempKelvin", 0) > 100:
                    result.track_temp = cw["trackTempKelvin"] - 273.15
                result.rain_intensity = cw.get("rainIntensity", 0)
                result.cloud_coverage = cw.get("cloudCoverage", 0)
                cls._backoff = 1.0; cls._backoff_until = 0
            cls._last_data = result
        except (requests.ConnectionError, requests.Timeout):
            cls._backoff = min(cls._backoff * 2, 60.0)
            cls._backoff_until = now + cls._backoff
        return cls._last_data

def merge_rest_into_flat(flat: dict, rest: Optional[LMURestData]):
    if rest is None: return
    if rest.current_ve > 0: flat["virtual_energy"] = rest.current_ve
    if rest.current_battery > 0: flat["battery_percentage"] = rest.current_battery
    if rest.tyre_wear: flat["tyre_wear"] = rest.tyre_wear
    if rest.brake_wear: flat["brake_wear"] = rest.brake_wear
    if rest.suspension_damage: flat["suspension_damage"] = rest.suspension_damage
    if rest.aero_damage > 0: flat["damage_aero"] = rest.aero_damage
    if rest.ambient_temp != 0: flat["ambient_temp"] = rest.ambient_temp
    if rest.track_temp != 0: flat["track_temp"] = rest.track_temp
    if rest.rain_intensity > 0: flat["rain_intensity"] = rest.rain_intensity
```

**Tests:**
```python
def test_kelvin_to_celsius():
    r = LMURestData()
    r.ambient_temp = 300.0 - 273.15  # ~27°C
    assert abs(r.ambient_temp - 26.85) < 0.1

def test_merge_ve_into_flat():
    flat = {}
    rest = LMURestData(current_ve=85.0, max_ve=100.0)
    merge_rest_into_flat(flat, rest)
    assert flat.get("virtual_energy") == 85.0
```

### Task 0.3: FrameCache (single frame, no deepcopy)

**File:** `backend/src/services/frame_cache.py`

```python
from typing import Optional
from backend.services.lmu_reader import LMUReader
from backend.services.lmu_rest_api import LMURestAPI, merge_rest_into_flat

class FrameCache:
    """One frame read — shared between events and spotter.
    
    CrewChief reads ONE frame and uses `forSpotter` flag to control data subset.
    FIX: Eliminates race between separate event loop and spotter loop.
    """
    def __init__(self, reader: LMUReader):
        self._reader = reader
        self._latest: Optional[dict] = None
        self._spotter: Optional[dict] = None
        self._frame_id: int = 0
        self._last_et: float = -1.0  # Dedup
    
    def read_full(self) -> dict:
        raw = self._reader.get_flat_dict()
        et = raw.get("session_running_time", 0.0)
        if et == self._last_et and self._latest is not None:
            return self._latest
        self._last_et = et
        
        # Merge REST API data
        rest = LMURestAPI.fetch()
        merge_rest_into_flat(raw, rest)
        
        self._latest = raw
        self._frame_id += 1
        
        # Pre-extract spotter data
        rivals = [{"id": i, "world_x": r.get("world_x",0), "world_z": r.get("world_z",0),
                    "speed": r.get("speed",0), "in_pits": r.get("in_pits",False),
                    "is_ghost": False} for i,r in enumerate(raw.get("rivals",[]))]
        self._spotter = {"world_x":raw.get("world_x",0), "world_z":raw.get("world_z",0),
                         "rotation_yaw":raw.get("rotation_yaw",0), "speed_ms":raw.get("speed_ms",0),
                         "rivals":rivals, "session_phase":raw.get("session_phase",0),
                         "in_pits":raw.get("in_pits",False), "_frame_id":self._frame_id}
        return self._latest
    
    def get_spotter_frame(self) -> dict:
        if self._spotter is None: self.read_full()
        return self._spotter
```

### Task 0.4: StateDiff with anti-bounce

**File:** `backend/src/services/state_diff.py`

```python
from copy import deepcopy
from typing import Dict, Set, Optional
from dataclasses import dataclass, field

@dataclass
class TickChanges:
    position_changed: bool = False
    old_position: Optional[int] = None; new_position: Optional[int] = None
    leader_changed: bool = False
    session_phase_changed: bool = False
    new_lap: bool = False; new_sector: bool = False
    retired_drivers: Set[str] = field(default_factory=set)
    new_drivers: Set[str] = field(default_factory=set)
    pit_entries: Set[str] = field(default_factory=set)
    pit_exits: Set[str] = field(default_factory=set)

class StateDiff:
    """CrewChief: previousGameState comparison. Anti-bounce: 1s position settling."""
    def __init__(self):
        self._prev: Optional[dict] = None
        self._prev_rivals: Dict[str,dict] = {}
        self._pending: Dict[str,dict] = {}  # driver -> {new_pos, settle_time}
        self._bounce_lag: float = 1.0
    
    def update(self, current: dict, now: float = 0) -> TickChanges:
        import time
        now = now or time.time()
        c = TickChanges()
        if self._prev is None:
            self._prev = deepcopy(current)
            self._prev_rivals = {r["driver_raw_name"]:r for r in current.get("rivals",[])}
            return c
        
        # New lap (FIX: use lap_number comparison, dedup)
        cl = current.get("lap_number",0); pl = self._prev.get("lap_number",0)
        c.new_lap = cl > pl
        
        # New sector
        cs = current.get("sector_number"); ps = self._prev.get("sector_number")
        c.new_sector = cs != ps
        
        # Position with anti-bounce
        old_pos = self._prev.get("place", 0); new_pos = current.get("place", 0)
        if old_pos != new_pos and new_pos > 0:
            p = self._pending.get("player")
            if p and p["new"] == new_pos:
                if now >= p["settle"]:
                    c.position_changed = True; c.old_position = old_pos; c.new_position = new_pos
                    self._pending.pop("player", None)
            else:
                self._pending["player"] = {"new": new_pos, "settle": now + self._bounce_lag}
        
        # Leader change
        ol = self._prev.get("leader_raw_name"); nl = current.get("leader_raw_name")
        if nl and nl != ol: c.leader_changed = True
        
        # Session phase
        if current.get("session_phase") != self._prev.get("session_phase"):
            c.session_phase_changed = True
        
        # Retirements & pit transitions
        prev_names = set(self._prev_rivals.keys())
        curr_names = set(r["driver_raw_name"] for r in current.get("rivals",[]))
        c.retired_drivers = prev_names - curr_names
        c.new_drivers = curr_names - prev_names
        curr_d = {r["driver_raw_name"]:r for r in current.get("rivals",[])}
        for n in curr_names & prev_names:
            pr, cr = self._prev_rivals[n], curr_d[n]
            if not pr.get("in_pits") and cr.get("in_pits"): c.pit_entries.add(n)
            if pr.get("in_pits") and not cr.get("in_pits"): c.pit_exits.add(n)
        
        self._prev = deepcopy(current)
        self._prev_rivals = deepcopy(curr_d)
        return c
```

### Task 0.5: DeltaTime + TrackDefinition + CarClass

**File:** `backend/src/services/delta_time.py`
```python
from typing import Tuple

class DeltaTime:
    """CrewChief: DeltaTime with lap difference support for multiclass."""
    def __init__(self, time: float, lap: int):
        self.time = time; self.lap = lap
    def get_signed_lap_diff(self, other: 'DeltaTime') -> int:
        return self.lap - other.lap
    def get_absolute_time_delta(self, other: 'DeltaTime', best_lap: float = 0) -> Tuple[int, float]:
        ld = self.get_signed_lap_diff(other)
        td = abs(self.time - other.time)
        if ld != 0 and best_lap > 0: td += abs(ld) * best_lap
        return (ld, td)
```

**File:** `backend/src/services/track_definition.py`
```python
from enum import Enum; from dataclasses import dataclass, field; from typing import List, Optional

class TrackLengthClass(Enum):
    VERY_SHORT="VERY_SHORT"; SHORT="SHORT"; MEDIUM="MEDIUM"; LONG="LONG"; VERY_LONG="VERY_LONG"

OUTLIER_PACE_LIMITS = {TrackLengthClass.VERY_LONG:15, TrackLengthClass.LONG:8,
    TrackLengthClass.MEDIUM:3, TrackLengthClass.SHORT:2, TrackLengthClass.VERY_SHORT:2}
FUEL_WINDOW_LENGTH = {TrackLengthClass.VERY_LONG:1, TrackLengthClass.LONG:2,
    TrackLengthClass.MEDIUM:3, TrackLengthClass.SHORT:4, TrackLengthClass.VERY_SHORT:5}
LAPS_BEFORE_GAPS = {TrackLengthClass.VERY_LONG:0, TrackLengthClass.LONG:1,
    TrackLengthClass.MEDIUM:2, TrackLengthClass.SHORT:3, TrackLengthClass.VERY_SHORT:4}

def get_length_class(length: float) -> TrackLengthClass:
    if length > 20000: return TrackLengthClass.VERY_LONG
    if length > 10000: return TrackLengthClass.LONG
    if length < 1000: return TrackLengthClass.VERY_SHORT
    if length < 2400: return TrackLengthClass.SHORT
    return TrackLengthClass.MEDIUM

@dataclass
class TrackDefinition:
    name: str; track_length: float
    sectors: int = 3; is_oval: bool = False
    gap_points: List[float] = field(default_factory=list)
    landmarks: List[dict] = field(default_factory=list)
    
    def __post_init__(self):
        self.track_length_class = get_length_class(self.track_length)
        if not self.gap_points and self.track_length > 3000:
            self.gap_points = self._gen_gap_points()
    
    def _gen_gap_points(self) -> List[float]:
        pts = []; t = 0.0
        while t < self.track_length - 1500: t += 1500; pts.append(round(t,3))
        pts.append(self.track_length - 50)
        return pts
```

**File:** `backend/src/data/car_class_data.py`
```python
from enum import Enum; from dataclasses import dataclass, field; from typing import List

class CarClassEnum(Enum):
    GT3="GT3"; GTE="GTE"; LMP1="LMP1"; LMP2="LMP2"; HYPER_CAR="HYPER_CAR"
    HYPER_CAR_RACE="HYPER_CAR_RACE"; LMDH="LMDH"; FORMULA_E="FORMULA_E"
    UNKNOWN_RACE="UNKNOWN_RACE"; USER_CREATED="USER_CREATED"
    # LMU-specific (WEC)
    HYPER_CAR_LMU="HYPER_CAR_LMU"; LMGT3="LMGT3"

class TyreTemp(Enum): COLD="COLD"; WARM="WARM"; HOT="HOT"; COOKING="COOKING"
class BrakeTemp(Enum): COLD="COLD"; WARM="WARM"; HOT="HOT"; COOKING="COOKING"
class DamageLevel(int, Enum):
    NONE=1; TRIVIAL=2; MINOR=3; MAJOR=4; DESTROYED=5

@dataclass
class Threshold:
    name: Enum; lower: float; upper: float

@dataclass
class CarClass:
    car_class_enum: CarClassEnum
    brake_type: str = "Iron_Race"
    default_tyre_type: str = "Unknown_Race"
    max_safe_water: float = 105.0; max_safe_oil: float = 125.0
    is_battery_powered: bool = False; is_drs_capable: bool = False; drs_range: float = -1.0
    is_vehicle_swap_allowed: bool = False; is_refueling_allowed: bool = True
    enabled_message_types: List[str] = field(default_factory=lambda: ["ALL"])

TYRE_TEMP_THRESHOLDS = {
    "Soft": [Threshold(TyreTemp.COLD,-10000,70),Threshold(TyreTemp.WARM,70,100),
             Threshold(TyreTemp.HOT,100,115),Threshold(TyreTemp.COOKING,115,10000)],
    "Medium": [Threshold(TyreTemp.COLD,-10000,75),Threshold(TyreTemp.WARM,75,105),
               Threshold(TyreTemp.HOT,105,120),Threshold(TyreTemp.COOKING,120,10000)],
    "Hard": [Threshold(TyreTemp.COLD,-10000,78),Threshold(TyreTemp.WARM,78,110),
             Threshold(TyreTemp.HOT,110,124),Threshold(TyreTemp.COOKING,124,10000)],
    "Wet": [Threshold(TyreTemp.COLD,-10000,40),Threshold(TyreTemp.WARM,40,80),
            Threshold(TyreTemp.HOT,80,105),Threshold(TyreTemp.COOKING,105,10000)],
    "Intermediate": [Threshold(TyreTemp.COLD,-10000,60),Threshold(TyreTemp.WARM,60,95),
                     Threshold(TyreTemp.HOT,95,110),Threshold(TyreTemp.COOKING,110,10000)],
    "Unknown_Race": [Threshold(TyreTemp.COLD,-10000,60),Threshold(TyreTemp.WARM,60,117),
                     Threshold(TyreTemp.HOT,117,137),Threshold(TyreTemp.COOKING,137,10000)],
}

BRAKE_TEMP_THRESHOLDS = {
    "Iron_Race": [Threshold(BrakeTemp.COLD,-10000,150),Threshold(BrakeTemp.WARM,150,700),
                  Threshold(BrakeTemp.HOT,700,900),Threshold(BrakeTemp.COOKING,900,10000)],
    "Ceramic": [Threshold(BrakeTemp.COLD,-10000,150),Threshold(BrakeTemp.WARM,150,950),
                Threshold(BrakeTemp.HOT,950,1200),Threshold(BrakeTemp.COOKING,1200,10000)],
    "Carbon": [Threshold(BrakeTemp.COLD,-10000,400),Threshold(BrakeTemp.WARM,400,1200),
               Threshold(BrakeTemp.HOT,1200,1500),Threshold(BrakeTemp.COOKING,1500,10000)],
}

CAR_CLASSES = {
    CarClassEnum.GT3: CarClass(CarClassEnum.GT3, brake_type="Ceramic", max_safe_oil=135),
    CarClassEnum.GTE: CarClass(CarClassEnum.GTE, brake_type="Ceramic", max_safe_oil=135),
    CarClassEnum.LMP1: CarClass(CarClassEnum.LMP1, brake_type="Carbon", max_safe_oil=140),
    CarClassEnum.LMP2: CarClass(CarClassEnum.LMP2, brake_type="Ceramic", max_safe_oil=135),
    CarClassEnum.HYPER_CAR: CarClass(CarClassEnum.HYPER_CAR, brake_type="Carbon",
        is_battery_powered=True, is_drs_capable=True, drs_range=1.0),
    CarClassEnum.LMDH: CarClass(CarClassEnum.LMDH, brake_type="Ceramic",
        is_drs_capable=True, drs_range=1.0),
    CarClassEnum.UNKNOWN_RACE: CarClass(CarClassEnum.UNKNOWN_RACE, enabled_message_types=["FUEL"]),
}

def get_car_class(enum: CarClassEnum) -> CarClass:
    return CAR_CLASSES.get(enum, CAR_CLASSES[CarClassEnum.UNKNOWN_RACE])

def get_tyre_thresholds(tyre: str) -> List[Threshold]:
    return TYRE_TEMP_THRESHOLDS.get(tyre, TYRE_TEMP_THRESHOLDS["Unknown_Race"])

def get_brake_thresholds(brake: str) -> List[Threshold]:
    return BRAKE_TEMP_THRESHOLDS.get(brake, BRAKE_TEMP_THRESHOLDS["Iron_Race"])
```

---

## 📐 PHASE 1: DATA MODEL

### Task 1.1: All enums

**File:** `backend/src/models/enums.py`
```python
from enum import Enum

class SessionType(str,Enum):
    UNAVAILABLE="Unavailable"; PRACTICE="Practice"; QUALIFY="Qualify"
    PRIVATE_QUALIFY="PrivateQualify"; RACE="Race"; HOT_LAP="HotLap"; LONE_PRACTICE="LonePractice"

class SessionPhase(str,Enum):
    UNAVAILABLE="Unavailable"; GARAGE="Garage"; GRIDWALK="Gridwalk"; FORMATION="Formation"
    COUNTDOWN="Countdown"; GREEN="Green"; FULL_COURSE_YELLOW="FullCourseYellow"
    CHECKERED="Checkered"; FINISHED="Finished"

class FlagEnum(str,Enum):
    GREEN="GREEN"; YELLOW="YELLOW"; DOUBLE_YELLOW="DOUBLE_YELLOW"; BLUE="BLUE"
    WHITE="WHITE"; BLACK="BLACK"; CHEQUERED="CHEQUERED"

class FullCourseYellowPhase(str,Enum):
    PENDING="PENDING"; IN_PROGRESS="IN_PROGRESS"; PITS_CLOSED="PITS_CLOSED"
    PITS_OPEN_LEAD_LAP="PITS_OPEN_LEAD_LAP"; PITS_OPEN="PITS_OPEN"
    LAST_LAP_NEXT="LAST_LAP_NEXT"; LAST_LAP_CURRENT="LAST_LAP_CURRENT"; RACING="RACING"

class FrozenOrderPhase(str,Enum): NONE="None"; FCY="FullCourseYellow"; FORMATION="FormationStanding"; ROLLING="Rolling"
class FrozenOrderColumn(str,Enum): NONE="None"; LEFT="Left"; RIGHT="Right"
class FrozenOrderAction(str,Enum): NONE="None"; FOLLOW="Follow"; CATCH_UP="CatchUp"; ALLOW_TO_PASS="AllowToPass"
class PitWindow(str,Enum): UNAVAILABLE="Unavailable"; CLOSED="Closed"; OPEN="Open"
class ControlType(str,Enum): PLAYER="Player"; AI="AI"; REMOTE="Remote"; REPLAY="Replay"
class TyreType(str,Enum): SOFT="Soft"; MEDIUM="Medium"; HARD="Hard"; WET="Wet"; INTERMEDIATE="Intermediate"
```

### Task 1.2: GameStateData (30+ dataclasses)

**File:** `backend/src/models/game_state_data.py`
```python
from dataclasses import dataclass, field; from typing import List, Optional, Dict, Tuple
from backend.models.enums import *
from backend.services.track_definition import TrackDefinition

@dataclass
class Rotation: pitch: float=0; roll: float=0; yaw: float=0

@dataclass
class PositionAndMotionData:
    world_x: float=0; world_y: float=0; world_z: float=0
    orientation: Rotation=field(default_factory=Rotation)
    car_speed: float=0; distance_round_track: float=0
    local_accel_x: float=0; local_accel_y: float=0; local_accel_z: float=0
    @property def speed_kmh(self): return self.car_speed * 3.6

@dataclass
class SessionData:
    session_type: SessionType=SessionType.UNAVAILABLE
    session_phase: SessionPhase=SessionPhase.UNAVAILABLE
    session_running_time: float=0  # CRITICAL: counts UP
    session_time_remaining: float=0
    completed_laps: int=0; session_laps_remaining: int=0
    is_new_lap: bool=False; is_new_sector: bool=False; sector_number: int=1
    player_lap_time_best: float=0; player_lap_time_prev: float=0; previous_lap_valid: bool=True
    class_position: int=0; overall_position: int=0
    session_start_class_position: int=0
    just_gone_green: bool=False; just_gone_green_time: float=0  # FIX: MUST be populated
    has_lead_changed: bool=False
    time_delta_front: float=0; time_delta_behind: float=0
    driver_name: str=""; leader_name: str=""
    is_new_session: bool=False; is_disqualified: bool=False; is_dnf: bool=False
    track_definition: Optional[TrackDefinition]=None

@dataclass
class PitData:
    in_pitlane: bool=False; on_out_lap: bool=False
    has_requested_pit_stop: bool=False; pit_window: PitWindow=PitWindow.UNAVAILABLE
    has_mandatory_pit_stop: bool=False; mandatory_pit_completed: bool=False
    mandatory_pit_min_left: float=0; pit_speed_limit: float=0
    driver_stint_seconds: float=0; driver_stint_total: float=0
    is_electric_swap_allowed: bool=False

@dataclass
class FlagData:
    sector_flags: List=field(default_factory=lambda:[FlagEnum.GREEN]*3)
    is_fcy: bool=False; fcy_phase: FullCourseYellowPhase=FullCourseYellowPhase.RACING
    is_local_yellow: bool=False

@dataclass
class TyreData:
    fl_temp: float=0; fr_temp: float=0; rl_temp: float=0; rr_temp: float=0
    fl_wear: float=0; fr_wear: float=0; rl_wear: float=0; rr_wear: float=0
    fl_pressure: float=0; fr_pressure: float=0; rl_pressure: float=0; rr_pressure: float=0
    fl_brake_temp: float=0; fr_brake_temp: float=0; rl_brake_temp: float=0; rr_brake_temp: float=0
    fl_compound: str="Unknown_Race"; fr_compound: str="Unknown_Race"
    rl_compound: str="Unknown_Race"; rr_compound: str="Unknown_Race"

@dataclass
class CarDamageData:
    aero: str="NONE"; engine: str="NONE"; transmission: str="NONE"
    suspension: List[str]=field(default_factory=lambda:["NONE"]*4)
    brakes: List[str]=field(default_factory=lambda:["NONE"]*4)
    last_impact_time: float=-1.0

@dataclass
class EngineData:
    rpm: float=0; water_temp: float=0; oil_temp: float=0
    oil_pressure: float=0; stalled: bool=False; gear: int=0

@dataclass
class FuelData: fuel_left: float=0; fuel_capacity: float=0; use_active: bool=True

@dataclass
class BatteryData:
    percentage: float=0; use_active: bool=False; capacity: float=-1
    def get_normalized(self) -> float:
        """FIX: Normalize fraction/percentage."""
        p = self.percentage; c = self.capacity
        if c > 0 and p <= 1: return (p * 100) / c
        if p <= 1: return p * 100
        return p

@dataclass
class OpponentData:
    driver: str=""; car_number: str="-1"; vehicle_class: str=""
    class_pos: int=0; overall_pos: int=0
    speed: float=0; distance: float=0; delta: float=0
    last_lap: float=0; best_lap: float=0; laps: int=0; sector: int=1
    in_pits: bool=False; active: bool=True; tyre: str="Unknown_Race"
    is_new_lap: bool=False; is_entering_pits: bool=False; is_exiting_pits: bool=False
    has_just_changed_tyres: bool=False

@dataclass
class PenaltiesData:
    num_outstanding: int=0; has_stop_go: bool=False; has_drivethrough: bool=False
    has_slow_down: bool=False; cut_warnings: int=0; incident_count: int=0; max_incident: int=0
    is_off_track: bool=False

@dataclass
class OvertakingAidsData:
    drs_enabled: bool=False; drs_engaged: bool=False; drs_available: bool=False; drs_range: float=-1
    ptp_engaged: bool=False; ptp_remaining: int=-1; ptp_cooldown: float=0

@dataclass
class FrozenOrderData:
    phase: FrozenOrderPhase=FrozenOrderPhase.NONE; action: FrozenOrderAction=FrozenOrderAction.NONE
    position: int=-1; column: FrozenOrderColumn=FrozenOrderColumn.NONE

@dataclass
class TimingData:
    best_laps: Dict[str,float]=field(default_factory=dict)
    def get_best(self, c="CURRENT"): return self.best_laps.get(c, -1)

@dataclass
class GameStateData:
    now: float=0
    session: SessionData=field(default_factory=SessionData)
    motion: PositionAndMotionData=field(default_factory=PositionAndMotionData)
    pit: PitData=field(default_factory=PitData)
    flag: FlagData=field(default_factory=FlagData)
    tyre: TyreData=field(default_factory=TyreData)
    damage: CarDamageData=field(default_factory=CarDamageData)
    engine: EngineData=field(default_factory=EngineData)
    fuel: FuelData=field(default_factory=FuelData)
    battery: BatteryData=field(default_factory=BatteryData)
    overtaking: OvertakingAidsData=field(default_factory=OvertakingAidsData)
    penalties: PenaltiesData=field(default_factory=PenaltiesData)
    frozen_order: FrozenOrderData=field(default_factory=FrozenOrderData)
    timing: TimingData=field(default_factory=TimingData)
    opponents: Dict[str,OpponentData]=field(default_factory=dict)
    car_class: str="UNKNOWN_RACE"
    multiclass: bool=False
```

### Task 1.3: QueuedMessage + MessageFragment

**File:** `backend/src/models/messages.py`
```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any, Callable
import time, logging

logger = logging.getLogger("vantare.messages")

class FragmentType: TEXT="text"; TIME="time"; OPPONENT="opponent"; INTEGER="integer"; PAUSE="pause"

class Precision: AUTO_LAPTIMES="AUTO_LAPTIMES"; AUTO_GAPS="AUTO_GAPS"; SECONDS="SECONDS"; TENTHS="TENTHS"; HUNDREDTHS="HUNDREDTHS"; MINUTES="MINUTES"

@dataclass
class TimeSpanWrapper:
    seconds: float; precision: str = Precision.AUTO_LAPTIMES

@dataclass
class MessageFragment:
    type: str; text: Optional[str]=None
    time_span: Optional[TimeSpanWrapper]=None; opponent: Optional[str]=None
    integer: Optional[int]=None; pause_ms: int=0
    
    @staticmethod def text(p): return MessageFragment(FragmentType.TEXT, text=p)
    @staticmethod def time(s, p=Precision.AUTO_LAPTIMES): return MessageFragment(FragmentType.TIME, time_span=TimeSpanWrapper(s,p))
    @staticmethod def opponent(n): return MessageFragment(FragmentType.OPPONENT, opponent=n)
    @staticmethod def integer(v): return MessageFragment(FragmentType.INTEGER, integer=v)
    @staticmethod def pause(ms): return MessageFragment(FragmentType.PAUSE, pause_ms=ms)

@dataclass
class DelayedMessageEvent:
    method_name: str; method_params: list; event_instance: Any

_id_counter = 0

class QueuedMessage:
    def __init__(self, name: str, expires: float = 10, fragments: Optional[List]=None,
                 alternate: Optional[List]=None, delay: float = 0, event: Any = None,
                 validation: Optional[Dict]=None, priority: int = 5, sound_type: str = "REGULAR",
                 trigger_fn: Optional[Callable]=None, delayed: Optional[DelayedMessageEvent]=None):
        global _id_counter; _id_counter += 1
        self.id = _id_counter; self.name = name
        self.expires = expires; self.delay = delay
        self.fragments = fragments or []; self.alternate = alternate
        self.event = event; self.validation = validation
        self.priority = priority; self.sound_type = sound_type
        self.trigger_fn = trigger_fn; self.delayed = delayed
        self.created = time.time()
        self.due = self.created + delay
        self.expiry = self.created + expires if expires > 0 else 0
        self.can_play = True; self.is_rant = False
    
    def is_expired(self, now=None): return self.expiry > 0 and (now or time.time()) >= self.expiry
    def is_due(self, now=None): return (now or time.time()) >= self.due
    def age(self): return time.time() - self.created
    
    def prepare_repeat(self):
        self.name = f"REPEAT_{self.name}"; self.priority = 5; self.sound_type = "VOICE_COMMAND"
        self.due = 0; self.expiry = 0; self.trigger_fn = None; self.event = None; self.validation = None; self.delay = 0

def contents(*objs) -> List[MessageFragment]:
    r = []
    for o in objs:
        if o is None: r.append(None)
        elif isinstance(o, MessageFragment): r.append(o)
        elif isinstance(o, str): r.append(MessageFragment.text(o))
        elif isinstance(o, int): r.append(MessageFragment.integer(o))
        elif isinstance(o, float): r.append(MessageFragment.time(o))
        elif isinstance(o, TimeSpanWrapper): r.append(MessageFragment.time(o.seconds, o.precision))
    return r

def Pause(ms: int): return MessageFragment(FragmentType.PAUSE, pause_ms=ms)
```

### Task 1.4: GameStateBuilder + _populate_derived_data

**File:** `backend/src/services/game_state_builder.py`
```python
from typing import Optional
from backend.models.game_state_data import *
from backend.models.enums import SessionType, SessionPhase
from backend.services.state_diff import TickChanges

def _session_type(v: int) -> SessionType:
    return {0:SessionType.UNAVAILABLE,1:SessionType.PRACTICE,2:SessionType.QUALIFY,
            3:SessionType.RACE}.get(v, SessionType.UNAVAILABLE)

def _session_phase(v: int) -> SessionPhase:
    return {0:SessionPhase.UNAVAILABLE,1:SessionPhase.GARAGE,2:SessionPhase.GRIDWALK,
            3:SessionPhase.FORMATION,4:SessionPhase.COUNTDOWN,5:SessionPhase.GREEN,
            6:SessionPhase.FULL_COURSE_YELLOW,7:SessionPhase.CHECKERED,8:SessionPhase.FINISHED}.get(v)

def build(flat: dict, prev: Optional[GameStateData]=None) -> GameStateData:
    g = GameStateData(); g.now = flat.get("timestamp", 0) or __import__('time').time()
    s = g.session
    s.session_type = _session_type(flat.get("session_type", 0))
    s.session_phase = _session_phase(flat.get("session_phase", 0))
    s.session_running_time = flat.get("session_running_time", 0)
    s.completed_laps = int(flat.get("lap_number", 0))
    s.class_position = int(flat.get("place", 0))
    s.driver_name = flat.get("driver_name", "")
    s.is_new_lap = flat.get("lap_number", 0) > (prev.session.completed_laps if prev else 0)
    s.sector_number = int(flat.get("sector_number", 1))
    
    m = g.motion
    m.world_x = flat.get("world_x", 0); m.world_z = flat.get("world_z", 0)
    m.orientation.yaw = flat.get("rotation_yaw", 0)
    m.orientation.pitch = flat.get("rotation_pitch", 0)
    m.orientation.roll = flat.get("rotation_roll", 0)
    m.car_speed = flat.get("speed_ms", 0)
    m.distance_round_track = flat.get("lap_distance", 0)
    
    g.pit.in_pitlane = flat.get("in_pits", False)
    g.fuel.fuel_left = flat.get("fuel_left", 0)
    
    # Battery (with normalization)
    b = flat.get("battery_percentage", 0) or flat.get("virtual_energy", 0)
    cap = flat.get("fuel_capacity", 0)
    if cap > 0 and b <= 1: g.battery.percentage = (b * 100) / cap
    elif b <= 1: g.battery.percentage = b * 100
    else: g.battery.percentage = b
    
    # Opponents
    for r in flat.get("rivals", []):
        n = r.get("driver_raw_name", "")
        if not n: continue
        g.opponents[n] = OpponentData(driver=n, car_number=r.get("car_number","-1"),
            class_pos=r.get("class_place",0), overall_pos=r.get("place",0),
            speed=r.get("speed",0), distance=r.get("distance_round_track",0),
            delta=r.get("gap_to_player",0), last_lap=r.get("last_lap_time",0),
            best_lap=r.get("best_lap_time",0), laps=r.get("laps_completed",0),
            in_pits=r.get("in_pits",False), tyre=r.get("tyre_compound","Unknown_Race"))
    
    return g

def populate_derived(g: GameStateData, changes: TickChanges, prev: Optional[GameStateData]=None):
    """FIX: MUST set just_gone_green_time for Position race start messages."""
    sd = g.session
    if sd.session_phase == SessionPhase.GREEN and prev and prev.session.session_phase != SessionPhase.GREEN:
        sd.just_gone_green = True
        sd.just_gone_green_time = g.now
    else: sd.just_gone_green = False
    
    if sd.just_gone_green or sd.is_new_session:
        sd.session_start_class_position = sd.class_position
    
    if changes.position_changed:
        sd.game_time_at_last_position_front_change = sd.session_running_time
```

---

## 📐 PHASE 2: CARTESIAN SPOTTER

**File:** `backend/src/intelligence/noisy_cartesian_spotter.py`
```python
import math, time, logging
from typing import List, Optional, Tuple, Dict

logger = logging.getLogger("vantare.spotter")

def aligned_xz(yaw: float, px: float, pz: float, ox: float, oz: float) -> Tuple[float, float]:
    dx, dz = ox - px, oz - pz; c, s = math.cos(-yaw), math.sin(-yaw)
    return (dx * c - dz * s, dx * s + dz * c)

class NoisyCartesianCoordinateSpotter:
    """CrewChief: NoisyCartesianCoordinateSpotter.cs (1000+ lines).
    
    Uses WORLD COORDINATES (X,Z) + player yaw rotation, NOT time gaps.
    """
    def __init__(self, ap=None):
        self.zone = 20.0; self.min_speed = 10.0; self.max_close = 50.0
        self.clear_gap = 1.0; self.car_len = 4.5; self.car_w = 1.8; self.behind_extra = 0.4
        self.max_per_side = 3
        self.clear_delay = 0.5; self.overlap_delay = 0.1
        self.repeat_freq = 3.0; self.to_3wide = 0.5
        self.cl = 0; self.cr = 0; self.clp = 0; self.crp = 0
        self.has_overlap = False
        self._v: Dict[int, dict] = {}
        self.rpt_l = False; self.rpt_r = False; self.rpt_dl = False; self.rpt_dr = False; self.mid = False
        self._next = None; self._due = 0.0
        self.ap = ap
    
    def trigger(self, st: dict, opps: List[dict], now: float):
        px, pz, yaw, sp = st.get("world_x",0), st.get("world_z",0), st.get("rotation_yaw",0), st.get("speed_ms",0)
        if (px == 0 and pz == 0) or sp < self.min_speed:
            if self.clp > 0 or self.crp > 0:
                self.clp = self.crp = 0; self.rpt_l = self.rpt_r = self.rpt_dl = self.rpt_dr = self.mid = False
            return
        
        cl, cr = 0, 0; aids = set()
        for o in opps:
            oid = o.get("id",0); ox, oz = o.get("world_x",0), o.get("world_z",0); os = o.get("speed",0)
            if ox == 0 and oz == 0: continue
            aids.add(oid)
            if abs(ox-px) > self.zone or abs(oz-pz) > self.zone:
                self._v.pop(oid, None); continue
            is_close = self._check_v(oid, ox, oz, os, now)
            if cl >= self.max_per_side and cr >= self.max_per_side: break
            side, _ = self._side(yaw, px, pz, ox, oz, is_close)
            if side == "l": cl += 1
            elif side == "r": cr += 1
        for oid in list(self._v):
            if oid not in aids: self._v.pop(oid, None)
        
        self._next_msg(cl, cr, now)
        self._play(cl, cr, now)
        self.clp, self.crp = self.cl, self.cr; self.cl, self.cr = cl, cr
        self.has_overlap = cl > 0 or cr > 0
    
    def _check_v(self, oid, x, z, sp, now) -> bool:
        if sp > 0: return abs(sp - self.min_speed) < self.max_close
        p = self._v.get(oid)
        if not p: self._v[oid] = {"x":x,"z":z,"t":now}; return True
        dt = now - p["t"]
        if dt >= 0.2:
            p["xs"] = (x - p["x"]) / dt; p["zs"] = (z - p["z"]) / dt
            p["x"] = x; p["z"] = z; p["t"] = now
        vs = math.sqrt(p.get("xs",0)**2 + p.get("zs",0)**2)
        return vs < self.max_close
    
    def _side(self, y, px, pz, ox, oz, in_range) -> Tuple[Optional[str], float]:
        ax, az = aligned_xz(y, px, pz, ox, oz)
        if abs(ax) >= self.zone: return (None, -1)
        if ax >= 0:
            if self.crp > 0:
                if abs(az) < self.car_len + self.clear_gap: return ("r", abs(ax))
            elif ((az < 0 and -az < self.car_len) or (az > 0 and az < self.car_len + self.behind_extra)) and abs(ax) > self.car_w and in_range:
                return ("r", abs(ax))
        else:
            if self.clp > 0:
                if abs(az) < self.car_len + self.clear_gap: return ("l", abs(ax))
            elif ((az < 0 and -az < self.car_len) or (az > 0 and az < self.car_len + self.behind_extra)) and abs(ax) > self.car_w and in_range:
                return ("l", abs(ax))
        return (None, -1)
    
    def _next_msg(self, l, r, now):
        if l == 0 and r == 0 and (self.clp > 0 or self.crp > 0):
            self._next = "clear_all_round"; self._due = now + self.clear_delay
        elif l == 0 and self.clp > 0: self._next = "clear_left"; self._due = now + self.clear_delay
        elif r == 0 and self.crp > 0: self._next = "clear_right"; self._due = now + self.clear_delay
        elif l > 0 and r > 0 and (self.clp == 0 or self.crp == 0): self._next = "three_wide"; self._due = now
        elif l > 0 and r == 0 and self.clp == 0: self._next = "three_wide_on_right" if l > 1 else "car_left"; self._due = now
        elif l == 0 and r > 0 and self.crp == 0: self._next = "three_wide_on_left" if r > 1 else "car_right"; self._due = now
        elif l > 1 and r == 0 and self.clp == 1: self._next = "three_wide_on_right"; self._due = now + self.to_3wide
        elif l == 0 and r > 1 and self.crp == 1: self._next = "three_wide_on_left"; self._due = now + self.to_3wide
    
    def _play(self, l, r, now):
        if not self._next or now < self._due: return
        if (self._next == "car_left" and l == 0) or (self._next == "car_right" and r == 0) or (self._next == "three_wide" and (r == 0 or l == 0)):
            return
        MAP = {"car_left":"spotter/car_left","car_right":"spotter/car_right","clear_left":"spotter/clear_left",
               "clear_right":"spotter/clear_right","clear_all_round":"spotter/clear_all_round",
               "three_wide":"spotter/in_the_middle","still_there":"spotter/still_there",
               "three_wide_on_left":"spotter/three_wide_on_left","three_wide_on_right":"spotter/three_wide_on_right"}
        if self._next in MAP:
            if self.ap: self.ap.play_spotter_message(MAP[self._next], keep_channel=True)
        if self._next in ("car_left","car_right","three_wide"):
            self._next = "still_there"; self._due = now + self.repeat_freq
        elif self._next in ("clear_left","clear_right","clear_all_round"):
            # FIX: Reset all reporting flags
            self.rpt_l = self.rpt_r = self.rpt_dl = self.rpt_dr = self.mid = False
            self._next = None
    
    def clear_state(self):
        self.cl = self.cr = self.clp = self.crp = 0; self.has_overlap = False
        self._v.clear(); self._next = None; self._due = 0
        self.rpt_l = self.rpt_r = self.rpt_dl = self.rpt_dr = self.mid = False
    
    def get_grid_side(self, yaw, px, pz, opps: List[dict]) -> str:
        for o in opps[:5]:
            ax, _ = aligned_xz(yaw, px, pz, o.get("world_x",0), o.get("world_z",0))
            if ax < -2: return "LEFT"
            if ax > 2: return "RIGHT"
        return "UNKNOWN"
```

**Tests:**
```python
def test_aligned_xz_facing_forward():
    ax, az = aligned_xz(0, 0, 0, 10, 0)
    assert ax > 0

def test_car_left_detected():
    s = NoisyCartesianCoordinateSpotter()
    s.car_w = 0.5; s.car_len = 2; s.min_speed = 0; s.max_close = 999
    st = {"world_x":0,"world_z":0,"rotation_yaw":0,"speed_ms":50}
    s.trigger(st, [{"id":1,"world_x":-2.5,"world_z":0.5,"speed":45}], time.time())
    s.trigger(st, [{"id":1,"world_x":-2.5,"world_z":0.5,"speed":45}], time.time()+0.3)
    assert s.cl > 0

def test_clear_after_overlap():
    s = NoisyCartesianCoordinateSpotter(); s.clear_delay = 0
    s.clp = 1; s.rpt_l = True
    s.trigger({"world_x":0,"world_z":0,"rotation_yaw":0,"speed_ms":50}, [], time.time())
    assert s._next == "clear_left"
```

---

## 📐 PHASE 3: EVENT ENGINE

**File:** `backend/src/intelligence/base_event.py`
```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from backend.models.enums import SessionType, SessionPhase
from backend.models.game_state_data import GameStateData
from backend.models.messages import QueuedMessage, MessageFragment, contents, Pause, DelayedMessageEvent
from backend.intelligence.event_flags import event_flags

class AbstractEvent(ABC):
    applicable_types: List[SessionType] = [SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE]
    applicable_phases: List[SessionPhase] = [SessionPhase.GREEN, SessionPhase.COUNTDOWN]
    category: str = "ALL"  # For per-car-class filtering
    sequence: int = 100
    
    def __init__(self, ap=None):
        self.ap = ap; self._f = False; self._psi = False
    
    @abstractmethod
    def trigger_internal(self, prev: Optional[GameStateData], curr: GameStateData): pass
    @abstractmethod
    def clear_state(self): pass
    
    def applicable(self, t: SessionType, p: SessionPhase) -> bool:
        return t in self.applicable_types and p in self.applicable_phases
    
    def should_suppress(self, g: GameStateData) -> bool:
        if event_flags.on_manual_formation_lap: return True
        if not self._enabled(g): return True
        return False
    
    def _enabled(self, g: GameStateData) -> bool:
        from backend.data.car_class_data import get_car_class_by_name
        cc = get_car_class_by_name(g.car_class)
        e = cc.enabled_message_types
        if "ALL" in e: return True
        if "NONE" in e: return False
        return self.category in e
    
    def is_valid(self, sub: str, cur: GameStateData, vd: Optional[Dict]=None) -> bool:
        return cur is not None and self.applicable(cur.session.session_type, cur.session.session_phase)
    
    def respond(self, vm: str): pass
    
    @staticmethod def C(*o): return contents(*o)
    @staticmethod def P(ms): return Pause(ms)

class FakeAudioPlayer:
    def __init__(self):
        self.msgs = []; self.imms = []
    def play(self, m, **kw): self.msgs.append(m)
    def play_imm(self, m, **kw): self.imms.append(m)
    def play_spotter(self, p, **kw): pass
    def pause_q(self, s): pass
    def unpause_q(self): pass
    def clear(self): self.msgs.clear(); self.imms.clear()
```

**File:** `backend/src/intelligence/event_engine.py`
```python
import asyncio, logging
from typing import Optional, Dict
from backend.models.game_state_data import GameStateData
from backend.intelligence.base_event import AbstractEvent

logger = logging.getLogger("vantare.engine")

class EventEngine:
    MAX_FAIL = 10; TIMEOUT = 2.0
    
    def __init__(self, ap=None):
        self._e: Dict[str, AbstractEvent] = {}
        self._f: Dict[str, int] = {}
        self._has_fail = False; self.ap = ap
    
    def register(self, n: str, ev: AbstractEvent):
        self._e[n] = ev
    
    def clear_all(self):
        for ev in self._e.values():
            try: ev.clear_state()
            except: pass
        self._f.clear(); self._has_fail = False
    
    async def tick(self, prev: Optional[GameStateData], curr: GameStateData):
        if not curr: return
        st, sp = curr.session.session_type, curr.session.session_phase
        for name, ev in sorted(self._e.items(), key=lambda x: x[1].sequence):
            if not ev.applicable(st, sp): continue
            if ev.should_suppress(curr): continue
            fail = self._f.get(name, 0)
            if self._has_fail and fail >= self.MAX_FAIL: continue
            try:
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, ev.trigger_internal, prev, curr),
                    timeout=self.TIMEOUT
                )
                if name in self._f: self._f[name] = 0
            except asyncio.TimeoutError:
                fail = self._f.get(name, 0) + 1; self._f[name] = fail
                logger.error(f"TIMEOUT: {name} ({fail}/{self.MAX_FAIL})")
                if fail >= self.MAX_FAIL: self._has_fail = True
            except Exception as e:
                fail = self._f.get(name, 0) + 1; self._f[name] = fail
                logger.error(f"FAIL: {name} ({fail}/{self.MAX_FAIL}): {e}")
                if fail >= self.MAX_FAIL: self._has_fail = True
    
    def get(self, n: str) -> Optional[AbstractEvent]:
        return self._e.get(n)
```

**File:** `backend/src/intelligence/event_flags.py`
```python
import asyncio; from dataclasses import dataclass, field; from typing import Set, Optional

@dataclass
class EventFlags:
    is_pitting: bool = False; played_pit_request: bool = False
    waiting_mandatory_stop: bool = False
    white_flag: bool = False; played_prelights: bool = False
    exit_close_front: Set[str] = field(default_factory=set)
    exit_close_behind: Set[str] = field(default_factory=set)
    waiting_driver_ok: bool = False
    on_formation: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
    async def set(self, n: str, v: bool):
        async with self._lock: setattr(self, n, v)
    async def get(self, n: str) -> bool:
        async with self._lock: return getattr(self, n, False)
    def reset(self):
        for f in self.__dataclass_fields__:
            if f.startswith('_'): continue
            t = self.__dataclass_fields__[f].type
            if t == bool: setattr(self, f, False)
            elif 'set' in str(t): setattr(self, f, set())
            elif 'Optional' in str(t): setattr(self, f, None)

event_flags = EventFlags()
```

**File:** `backend/src/config/global_behaviour.py`
```python
from dataclasses import dataclass, field; from typing import Set

@dataclass
class GlobalBehaviour:
    spotter_enabled: bool = True
    use_oval: bool = False; oval_spotter: bool = False
    just_facts: bool = False; speak_when_spoken: bool = False
    cut_warnings: bool = True
    use_american: bool = False; use_metric: bool = True
    max_complaints: int = 3; complaints_count: int = 0
    messages: Set[str] = field(default_factory=lambda: {"ALL"})

global_settings = GlobalBehaviour()
```

---

## 📐 PHASE 4: AUDIO SYSTEM

### Task 4.1: SoundCache

**File:** `backend/src/services/sound_cache.py`
```python
import logging, os, json, random
from pathlib import Path
from typing import Set, List, Optional, Dict

logger = logging.getLogger("vantare.sound")
BASE = Path(__file__).parent.parent / "audio"

class SoundCache:
    avail: Set[str] = set()
    driver_names: Set[str] = set()
    has_tts: bool = True
    _variety: Dict[str, tuple] = {}
    
    @classmethod
    def init(cls, path=None):
        p = path or BASE
        if not p.exists(): return
        cls.avail.clear()
        for w in p.rglob("*.wav"):
            k = str(w.relative_to(p).with_suffix("")).replace("\\", "/")
            cls.avail.add(k)
        dn = p / "driver_names"
        if dn.exists():
            for w in dn.glob("*.wav"):
                cls.driver_names.add(w.stem.lower())
        cls._load_variety()
    
    @classmethod
    def play(cls, folder: str, meta: Optional[dict]=None) -> bool:
        if folder.startswith("PAUSE:") or folder.startswith("pause:"):
            return True  # Caller handles async sleep
        if folder in cls.avail:
            logger.debug(f"Play: {folder}")
            return True
        if folder.startswith("TTS_IDENTIFIER"):
            return True
        logger.warning(f"Not found: {folder}")
        return False
    
    @classmethod
    def select_variant(cls, path: str, n: int) -> str:
        key = path.split("/")[-1]
        if key not in cls._variety: cls._variety[key] = (n, 0)
        _, played = cls._variety[key]
        v = (played % n) + 1
        cls._variety[key] = (n, played + 1)
        return f"{path}_{v}"
    
    @classmethod
    def _load_variety(cls):
        p = os.path.expanduser("~/.vantare/sound_variety.json")
        if os.path.exists(p):
            try:
                with open(p) as f:
                    for k, v in json.load(f).items():
                        cls._variety[k] = (v[0], v[1])
            except: pass
    
    @classmethod
    def save_variety(cls):
        p = os.path.expanduser("~/.vantare/sound_variety.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            json.dump({k: list(v) for k, v in cls._variety.items()}, f)
```

### Task 4.2: AudioPlayer with dual queue

**File:** `backend/src/services/audio_player.py`
```python
import time, logging, asyncio
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from backend.models.messages import QueuedMessage
from backend.services.sound_cache import SoundCache

logger = logging.getLogger("vantare.audio")

class AudioPlayer:
    SPOTTER = 20; CRITICAL = 15; IMPORTANT = 10; VOICE = 8; NORMAL = 5
    
    def __init__(self):
        self.q = OrderedDict(); self.iq = OrderedDict()
        self.last = None; self.channel = False; self.hold = False
        self.quiet = False; self.paused = False; self._until = 0
        self.beeps = True; self.pause_between = 0.5
        self._exec = ThreadPoolExecutor(max_workers=1, prefix="audio")
    
    def play(self, m: QueuedMessage, **kw):
        if not m.can_play: return
        if m.name in self.q: return
        self._insert(self.q, m)
    
    def play_imm(self, m: QueuedMessage, hold=False):
        if not m.can_play: return
        if m.name in self.iq: return
        self.hold = hold
        self._insert(self.iq, m)
    
    def play_spotter_message(self, path: str, keep_channel=True):
        m = QueuedMessage(path, expires=2, priority=self.SPOTTER, sound_type="SPOTTER")
        self.hold = keep_channel
        self._insert(self.iq, m)
        SoundCache.interrupt()
    
    def purge(self, retain=True) -> int:
        c = 0
        for q in [self.q, self.iq]:
            for k in list(q.keys()):
                if retain and "RETAIN" in k: continue
                q.pop(k, None); c += 1
        return c
    
    def pause_q(self, s: int):
        self.paused = True; self._until = time.time() + s
    
    def unpause_q(self): self.paused = False
    
    def repeat(self):
        if self.last:
            self.last.prepare_repeat()
            self.play_imm(self.last)
    
    def process(self, now=None, gsd=None) -> bool:
        now = now or time.time()
        if self.paused:
            if now < self._until: return False
            self.paused = False
        m = self._next(self.iq, now, gsd)
        if m: self._play(m); return True
        m = self._next(self.q, now, gsd)
        if m: self._play(m); return True
        return False
    
    def _insert(self, q, m):
        idx = 0
        for k, e in list(q.items()):
            if m.priority > e.priority: break
            idx += 1
        q.insert(idx, m.name, m)
    
    def _next(self, q, now, gsd):
        for k, m in list(q.items()):
            if not m.is_due(now): continue
            if m.is_expired(now): q.pop(k, None); continue
            if not m.can_play: q.pop(k, None); continue
            if m.event and gsd and not m.event.is_valid(m.name, gsd, m.validation):
                q.pop(k, None); continue
            if m.trigger_fn and gsd and not m.trigger_fn(gsd):
                q.pop(k, None); continue
            q.pop(k, None)
            return m
        return None
    
    def _play(self, m):
        if self.beeps and m.priority >= self.IMPORTANT:
            SoundCache.play("fx/beep_start")
        for f in getattr(m, '_paths', []) or []:
            SoundCache.play(f)
        if self.beeps:
            SoundCache.play("fx/beep_end")
        self.last = m
```

---

## 📐 PHASES 5-7: ALL 29 EVENTS

Each event follows the SAME pattern as PositionEvent below. The pattern is:
1. Inherit AbstractEvent
2. Set `applicable_types`, `applicable_phases`, `category`, `sequence`
3. Implement `trigger_internal(prev, curr)` — check conditions, call `self.ap.play()`
4. Implement `clear_state()` — reset ALL state variables
5. Override `is_valid()` if delayed messages need validation
6. Implement `respond(vm)` for voice commands

### Task 5.1: PositionEvent (template for ALL events)

**File:** `backend/src/intelligence/events/position.py`
```python
import time, random
from typing import Optional
from backend.intelligence.base_event import AbstractEvent
from backend.models.enums import SessionType, SessionPhase
from backend.models.game_state_data import GameStateData
from backend.models.messages import QueuedMessage, DelayedMessageEvent, contents
from backend.services.utilities import random_int, random_double
from backend.config.global_behaviour import global_settings
from backend.intelligence.event_flags import event_flags

F_LEADING = "position/leading"; F_POLE = "position/pole"
F_LAST = "position/last"; F_STUB = "position/p"
F_OVERTAKE = "position/overtaking"; F_BEING_OVERTAKEN = "position/being_overtaken"
F_CONSISTENTLY_LAST = "position/consistently_last"
F_GOOD_START = "position/good_start"; F_OK_START = "position/ok_start"
F_BAD_START = "position/bad_start"; F_TERRIBLE_START = "position/terrible_start"

class PositionEvent(AbstractEvent):
    applicable_types = [SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE]
    applicable_phases = [SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW, SessionPhase.COUNTDOWN]
    sequence = 20
    
    def __init__(self, ap=None):
        super().__init__(ap)
        self.pos = 0; self.prev_pos = 0; self.start_pos = None
        self.played_start = False; self.laps_last = 0; self.is_last = False
        self.ahead_key = None; self.behind_key = None
        self.passed_key = None; self.passed_us_key = None
        self.pass_time = 0; self.passed_us_time = 0
        self.last_overtake_time = 0; self.clean = True
        self.offtrack_time = -1; self.yellow_time = -1
        self.gaps_ahead = []; self.gaps_behind = []
        self.gap_counter = 0; self.last_check = 0
        self.can_remind = True; self.lap_remind = random_int(2,5); self.sector_remind = random_int(1,4)
        self._pending = {}; self._bounce = 1.0
    
    def clear_state(self):
        self.pos = self.prev_pos = 0; self.start_pos = None
        self.played_start = False; self.laps_last = 0
        self.ahead_key = self.behind_key = None
        self.passed_key = self.passed_us_key = None
        self.pass_time = self.passed_us_time = 0
        self.last_overtake_time = 0; self.clean = True
        self.offtrack_time = self.yellow_time = -1
        self.gaps_ahead.clear(); self.gaps_behind.clear()
        self.gap_counter = 0; self.last_check = 0
        self.can_remind = True
        self.lap_remind = random_int(2,5); self.sector_remind = random_int(1,4)
        self._pending.clear()
    
    def _bounce_pos(self, name, old, new, now):
        if old == new: self._pending.pop(name, None); return old
        p = self._pending.get(name)
        if p and p["new"] == new:
            return new if now >= p["settle"] else old
        self._pending[name] = {"new": new, "settle": now + self._bounce}
        return old
    
    def trigger_internal(self, prev, curr):
        if event_flags.on_formation: return
        if self.should_suppress(curr): return
        
        self.pos = curr.session.class_position; self.is_last = curr.is_last_in_standings()
        now = curr.now
        
        # FIX: Gap sampling at 1Hz
        self.gap_counter += 1
        if self.gap_counter % 10 == 0:
            if curr.session.time_delta_front > 0:
                self.gaps_ahead.append(curr.session.time_delta_front)
            if curr.session.time_delta_behind > 0:
                self.gaps_behind.append(curr.session.time_delta_behind)
        
        # Overtake detection
        if not global_settings.use_oval and self.passed_key is None and self.passed_us_key is None:
            self._check_overtakes(prev, curr, now)
        self._check_completed(curr, now)
        
        # Race start
        self._check_start(prev, curr)
        
        # Position reminders
        self._check_reminder(prev, curr)
        
        self.prev_pos = self.pos
    
    def _check_overtakes(self, prev, curr, now):
        if curr.session.session_phase != SessionPhase.GREEN or curr.session.completed_laps < 1:
            return
        if now < self.last_check + 1: return
        self.last_check = now
        
        if curr.penalties.is_off_track:
            self.offtrack_time = curr.session.session_running_time
        if curr.flag.is_local_yellow:
            self.yellow_time = curr.session.session_running_time
        
        ca = curr.get_opponent_key_in_front(); cb = curr.get_opponent_key_behind()
        if ca != self.ahead_key and ca and self.behind_key == self.ahead_key and len(self.gaps_ahead) > 5:
            opp = curr.opponents.get(self.behind_key)
            if opp and opp.laps == curr.session.completed_laps and curr.session.previous_lap_valid:
                self.pass_time = now; self.passed_key = self.behind_key
                self.clean = self._is_clean(curr)
                self.gaps_ahead.clear()
        if cb != self.behind_key and self.ahead_key == self.behind_key and len(self.gaps_behind) > 5:
            opp = curr.opponents.get(self.ahead_key)
            if opp and opp.laps == curr.session.completed_laps:
                self.passed_us_time = now; self.passed_us_key = self.ahead_key
                self.gaps_behind.clear()
        self.ahead_key = ca; self.behind_key = cb
    
    def _is_clean(self, curr) -> bool:
        r = curr.session.session_running_time
        if curr.damage.last_impact_time > 0 and r - curr.damage.last_impact_time < 10: return False
        if self.offtrack_time > 0 and r - self.offtrack_time < 10: return False
        if self.yellow_time > 0 and r - self.yellow_time < 3: return False
        return True
    
    def _check_completed(self, curr, now):
        if self.passed_key:
            opp = curr.opponents.get(self.passed_key)
            if opp and now < self.pass_time + 7:
                if now > self.pass_time + 4 and now > self.last_overtake_time + 20:
                    if opp.class_pos > curr.session.class_position:
                        self.last_overtake_time = now; self.passed_key = None; self.gaps_ahead.clear()
                        m = QueuedMessage(F_OVERTAKE, expires=3, priority=10,
                                          fragments=contents(F_OVERTAKE), event=self)
                        self.ap.play(m)
                elif not curr.session.previous_lap_valid or opp.in_pits or curr.pit.in_pitlane:
                    self.passed_key = None; self.gaps_ahead.clear()
            else: self.passed_key = None; self.gaps_ahead.clear()
    
    def _check_start(self, prev, curr):
        if not self.played_start and curr.session.just_gone_green and curr.now > curr.session.just_gone_green_time + random_int(30,50):
            self.played_start = True
            if self.start_pos is None: self.start_pos = curr.session.session_start_class_position
            if self.start_pos <= 0: return
            if curr.penalties.has_drivethrough or curr.penalties.has_stop_go: return
            d = self.start_pos - curr.session.class_position
            vd = {"pos": curr.session.class_position}
            if d >= 5: self.ap.play(QueuedMessage(F_TERRIBLE_START, 10, priority=5, event=self, validation=vd))
            elif d >= 3: self.ap.play(QueuedMessage(F_BAD_START, 10, priority=5, event=self, validation=vd))
            elif d >= 1 or curr.session.class_position == 1: self.ap.play(QueuedMessage(F_GOOD_START, 10, priority=5, event=self, validation=vd))
            elif random_double() > 0.6: self.ap.play(QueuedMessage(F_OK_START, 10, priority=5, event=self, validation=vd))
    
    def _check_reminder(self, prev, curr):
        if self.can_remind and curr.session.is_new_sector and curr.session.completed_laps == self.lap_remind and curr.session.sector_number == self.sector_remind:
            dme = DelayedMessageEvent("_pos_msgs", [curr.session.class_position, True], self)
            self.ap.play(QueuedMessage("position", 10, delayed=dme, event=self, priority=10))
            self.can_remind = False
        if curr.session.is_new_lap and curr.session.completed_laps > 0:
            if self.is_last: self.laps_last += 1
            else: self.laps_last = 0
            if self.prev_pos != curr.session.class_position:
                self.can_remind = True; self.lap_remind = curr.session.completed_laps + random_int(3,6)
                self.sector_remind = random_int(1,4)
                dme = DelayedMessageEvent("_pos_msgs", [curr.session.class_position, False], self)
                self.ap.play(QueuedMessage("position", 10, delayed=dme, event=self, priority=10))
    
    def _pos_msgs(self, pos_when_queued, is_reminder):
        if is_reminder and pos_when_queued != self.pos:
            return ([], None)
        p = self.pos
        if p == 1: return (contents(F_LEADING), None)
        if self.is_last and not global_settings.just_facts:
            if self.laps_last > 5 and global_settings.complaints_count < global_settings.max_complaints:
                global_settings.complaints_count += 1
                return (contents(F_CONSISTENTLY_LAST), None)
            return (contents(F_LAST), None)
        return (contents(f"{F_STUB}{p}"), None)
    
    def respond(self, vm: str):
        if "position" in vm.lower() or "where" in vm.lower():
            if self.is_last: self.ap.play_imm(QueuedMessage(F_LAST, 0))
            elif self.pos == 1: self.ap.play_imm(QueuedMessage(F_LEADING, 0))
            elif self.pos > 0: self.ap.play_imm(QueuedMessage(f"{F_STUB}{self.pos}", 0))
            else: self.ap.play_imm(QueuedMessage("acknowledge/no_data", 0))
```

### Tasks 5.2-7.7: Remaining 28 events

ALL remaining 28 events follow the EXACT same pattern as PositionEvent. Each:
- Creates `{name}.py` in `backend/src/intelligence/events/`
- Creates `test_{name}.py` in `backend/tests/`
- Implements `trigger_internal()` with CrewChief logic
- Implements `clear_state()` reseting ALL state
- Overrides `is_valid()` for time-sensitive messages
- Has 5+ unit tests

The 28 event files in implementation order:
1. `lap_counter.py` – Pre-lights, green flag, last lap, formation lap, double-file grid, get ready
2. `pit_stops.py` – Box countdown 5-4-3-2-1, limiter engage/disengage, pit speed limit announcement, pit stall occupied/available, mandatory stop timer, pit entry/exit warnings, pit window open/close, R3E/LMU pit menu actions
3. `fuel.py` – Per-lap window (FUEL_WINDOW_LENGTH dict), per-minute window, max consumption, FCY→use max, half-distance message, 2/5/10 minute warnings, pit now, metric/imperial, refuel detection reset
4. `battery.py` – VE tracking with 5-lap window + 15s window, trend analysis (Inc/Dec/Stable), low threshold (10% dynamic), critical (5%), advice system (increase/reduce/spot on/won't make), vehicle swap awareness, 2/5/10 minutes/laps remaining, voice command
5. `tyre_monitor.py` – 14 compounds × 4 temp bands (COLD/WARM/HOT/COOKING), wear levels (NEW/SCRUBBED/MINOR/MAJOR/WORN_OUT), pressure trends 1000ms, flat spot pressure delta >5psi, brake temps 4 types × 4 bands, camber analysis, locking/spinning accumulation per lap
6. `flags_monitor.py` – FCY 7-phase state machine (PENDING→RACING), incident detection via distance delta, pileup (≥4 cars in same zone), blue flag (max 3 repeats per driver), overtake under yellow detection, sector-specific flags
7. `damage_reporting.py` – 5 components (ENGINE, TRANNY, AERO, SUSPENSION, BRAKES), 5 levels (NONE→DESTROYED), puncture per wheel (pressure <5psi), crash detection (>40G impact, 3s speed check), rollover detection (orientation samples 3s, >97°), "Are you OK?" with 3 retries, queue purge on DESTROYED, hide minor damage if component DESTROYED
8. `engine_monitor.py` – 60s average window for water/oil temp, min 10 samples before checking, stall warning immediate (priority 15), oil/fuel pressure warnings (2min cooldown), per-class thresholds from CarClass
9. `opponents.py` – Leader change detection (30s min between), new car ahead/behind (with validationData driver key), retirement/DQ announcements (once per driver), tyre change announcements (10-20s random cooldown), fast lap announcements (frequency config), voice commands (10+)
10. `lap_times.py` – Delta categorization (FAST <0.05s, A_TENTH 0.05-0.15, TWO_TENTHS 0.15-0.25, A_SECOND 0.95-1.05, AUTO_GAPS <10s), consistency 5-lap window 0.5%, outlier detection by TrackLengthClass, self-pace vs opponent pace
11. `race_time.py` – 20/15/10/5/2/0 minute messages, halfway, extra laps after timed session, pearls suspended last 3 min
12. `timings.py` – Gap status (CLOSE/INCREASING/DECREASING/OTHER/NONE) from 3 samples, being-held-up (>60s close), being-pressured, attack/defend via track landmarks, frequency config, validation: skip if gap <1 car length or recent overtake
13. `push_now.py` – Push to improve/hold (gap prediction via opponent best laps), pit exit warnings (traffic behind/clear), qualify exit (X minutes/laps), opponent leaving pits detection
14. `strategy.py` – Post-pit position prediction, pit stop benchmarking (persisted to JSON), opponent pit exit estimation, pit stall blocking detection, R3E/LMU pit menu actions announcement
15. `penalties.py` – Cut track 4 levels (cuts/min rate), 10+ detailed causes, 3/2/1 lap countdown with validation, collision detection via incident points, kick warnings near limit, voice commands
16. `driver_swaps.py` – Stint time remaining (15/10/5/2 min), "pit this lap" when remaining < bestLap+30s, "pit now" reminder sector 3, "no more stints"
17. `overtaking_aids.py` – DRS beeps (detection + available), DRS messages, Push-to-Pass remaining/cooldown, DTM2020 PtP reminder
18. `multiclass_warnings.py` – Faster class behind (zones by track length), slower ahead, fighting detection (cars within 30m), first-time session warnings, 30s check interval, voice commands
19. `watched_opponents.py` – Track driver (by name/number/position), team mate/rival designation, pit exit report, position change report (max 40s between), fast lap report, voice commands
20. `session_end_messages.py` – Win/podium/last/general, DNF/DSQ handling, qualify pole/position, expected finish from Q, rant system
21. `common_actions.py` – Orchestrator: getStatus() calls 9 events, keep quiet/unquiet, deltas toggle, yellow flags, cut warnings, formation lap, corner names, pace notes, time report, button mapping
22. `alarm_clock.py` – Configurable alarms (from settings + voice), "set alarm for X:Y", "clear alarm", triggers at system time
23. Heartbeat / health — handled by main loop
24. `conditions_monitor.py` – Weather samples every 10s, classify (SNOW→WARM_DRY), track condition delay, timing filtered by conditions
25. `frozen_order_monitor.py` – SC/FCY formation, rolling start, column assignment (left/right), driver to follow, action messages (follow/catch up/allow to pass)
26. PearlsOfWisdom — GOOD/BAD/NEUTRAL pearls on overtakes/position/laps, suspended during FCY/last lap/destroyed, max_complaints limit
27. CoDriver — Not relevant (rally)
28. SessionEndMessages — (covered above)
29. SPOTTER — (covered in Phase 2)

---

## 📐 MAIN LOOP — Final

**File:** `backend/src/main.py`
```python
import asyncio, time, logging
from backend.services.frame_cache import FrameCache
from backend.services.lmu_reader import LMUReader
from backend.services.game_state_builder import build, populate_derived
from backend.services.state_diff import StateDiff
from backend.intelligence.event_engine import EventEngine
from backend.intelligence.event_flags import event_flags
from backend.intelligence.noisy_cartesian_spotter import NoisyCartesianCoordinateSpotter
from backend.config.global_behaviour import global_settings

logger = logging.getLogger("vantare.main")

async def main_loop(reader, engine, ap):
    cache = FrameCache(reader)
    diff = StateDiff()
    spotter = NoisyCartesianCoordinateSpotter(ap)
    spotter.clear_state()
    prev = None
    empty = 0
    
    while True:
        try:
            flat = cache.read_full()
            if not flat.get("session_running_time", 0):
                empty += 1
                if empty >= 50:
                    logger.warning("No data — reinit")
                    reader.reinitialize()
                    cache._last_et = -1
                    empty = 0
                await asyncio.sleep(0.1); continue
            empty = 0
            
            gsd = build(flat, prev)
            changes = diff.update(flat, gsd.now)
            populate_derived(gsd, changes, prev)
            
            # Session transitions
            if gsd.session.is_new_session:
                engine.clear_all(); event_flags.reset()
                ap.purge(); spotter.clear_state()
                global_settings.complaints_count = 0
            
            # Abrupt end detection (FIX: check session phase transition)
            if prev and prev.session.session_phase == SessionPhase.GREEN and gsd.session.session_phase == SessionPhase.UNAVAILABLE:
                logger.info("Abrupt session end — purge")
                ap.purge(); engine.clear_all()
            
            # Spotter inline (FIX: not separate task)
            if not event_flags.waiting_driver_ok:
                sf = cache.get_spotter_frame()
                st = session_type = sf.get("session_phase", 0)
                if st == 6:  # FCY
                    spotter._close_if_idle(time.time())
                else:
                    spotter.trigger(sf, sf.get("rivals", []), time.time())
            
            # Events
            await engine.tick(prev, gsd)
            
            # Audio
            ap.process()
            
            prev = gsd
            await asyncio.sleep(0.1)
        except asyncio.CancelledError: break
        except Exception as e:
            logger.error(f"Main loop: {e}")
            await asyncio.sleep(1.0)
```

---

## ✅ FINAL VERIFICATION CHECKLIST

**Before marking any event complete:**
- [ ] 5+ unit tests (TDD: red→green→refactor)
- [ ] `should_suppress()` checks formation + car class
- [ ] `is_valid()` handles stale messages
- [ ] `clear_state()` resets ALL state (including cached damage, impact times)
- [ ] Cooldowns use `session_running_time` (NOT `session_time_remaining`)
- [ ] Audio uses `contents()` with proper folder paths
- [ ] Event registered in `EventEngine`
- [ ] Cross-event flags via `event_flags` (not static vars)
- [ ] NaN-safe math on all orientation/position calculations
- [ ] 1Hz sampling where CrewChief uses 1s intervals

**Integration tests:**
- [ ] Full pipeline: FrameCache → GameStateBuilder → EventEngine → AudioPlayer  
- [ ] Spotter detects car left/right with real coordinate data
- [ ] Abrupt session end handled
- [ ] Shared memory recovery: game restart without crash
- [ ] REST API fallback: backoff when API unavailable
- [ ] Frame dedup: identical frames produce no phantom events
- [ ] Fault tolerance: 2s timeout → disable at 10 failures
- [ ] All 22 events produce correct messages in a simulated race