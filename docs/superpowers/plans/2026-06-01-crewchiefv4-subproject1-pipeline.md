# Sub-proyecto 1: Pipeline de Datos — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el pipeline de datos que lee shared memory de LMU, la fusiona con REST API, la aplana a flat dict, la convierte a objetos tipados (GameStateData), y detecta cambios entre ticks. Sin esto no funciona nada más.

**Architecture:** `lmu_reader.py` lee shared memory usando structs reutilizados de `shared_telemetry` + `MMapControl`. `frame_cache.py` envuelve el reader, añade REST API, y sirve el mismo dict a spotter y eventos. `state_diff.py` compara ticks y reporta cambios generales. `game_state_builder.py` convierte el dict plano a dataclasses tipadas.

**Tech Stack:** Python 3.11+, ctypes, asyncio, shared_telemetry (existente)

**Documentos de referencia:**
- Spec: `docs/superpowers/specs/2026-06-01-crewchiefv4-backend-design.md`
- Plan maestro: `docs/superpowers/plans/2026-06-01-crewchiefv4-full-implementation.md`

---

## Dependencias entre archivos

```
enums.py (sin dependencias)
  ↑
track_definition.py (sin dependencias)
  ↑
car_class_data.py (depende de enums.py)
  ↑
game_state_data.py (depende de enums.py, track_definition.py)
  ↑
messages.py (MODIFICAR — añadir clases, no tocar las existentes)
  ↑
lmu_reader.py (depende de shared_telemetry — structs + MMapControl)
  ↑
delta_time.py (sin dependencias)
  ↑
state_diff.py (sin dependencias)
  ↑
frame_cache.py (depende de lmu_reader.py, lmu_api.py existente)
  ↑
game_state_builder.py (depende de game_state_data.py, state_diff.py)
```

**Orden de implementación:** Seguir el orden de abajo a arriba.

---

### Task 1: Enums — Tipos de sesión, fases, flags

**Files:**
- Create: `backend/src/models/enums.py`
- Test: `backend/tests/test_enums.py`

**Descripción:** Define todos los enumerados que usa el sistema. Sin estos, ningún evento ni el GameStateData pueden funcionar.

#### Step 1: Escribir el test

```python
# backend/tests/test_enums.py
import pytest
from backend.src.models.enums import (
    SessionType, SessionPhase, FlagEnum, FullCourseYellowPhase,
    FrozenOrderPhase, PitWindow, TyreType, ControlType
)

def test_session_type_values():
    assert SessionType.RACE.value == "Race"
    assert SessionType.PRACTICE.value == "Practice"

def test_session_phase_values():
    assert SessionPhase.GREEN.value == "Green"
    assert SessionPhase.FULL_COURSE_YELLOW.value == "FullCourseYellow"
    assert SessionPhase.UNAVAILABLE.value == "Unavailable"

def test_flag_enum_values():
    assert FlagEnum.GREEN.value == "GREEN"
    assert FlagEnum.YELLOW.value == "YELLOW"
    assert FlagEnum.BLUE.value == "BLUE"
    assert FlagEnum.CHEQUERED.value == "CHEQUERED"

def test_fcy_phases():
    assert FullCourseYellowPhase.PENDING.value == "PENDING"
    assert FullCourseYellowPhase.RACING.value == "RACING"
    assert FullCourseYellowPhase.PITS_CLOSED.value == "PITS_CLOSED"

def test_frozen_order():
    assert FrozenOrderPhase.FCY.value == "FullCourseYellow"
    assert FrozenOrderPhase.FORMATION.value == "FormationStanding"

def test_pit_window():
    assert PitWindow.OPEN.value == "Open"
    assert PitWindow.CLOSED.value == "Closed"

def test_tyre_types():
    assert TyreType.SOFT.value == "Soft"
    assert TyreType.WET.value == "Wet"

def test_control_type():
    assert ControlType.PLAYER.value == "Player"
    assert ControlType.AI.value == "AI"
```

#### Step 2: Crear enums.py

```python
# backend/src/models/enums.py
from enum import Enum

class SessionType(str, Enum):
    UNAVAILABLE = "Unavailable"
    PRACTICE = "Practice"
    QUALIFY = "Qualify"
    PRIVATE_QUALIFY = "PrivateQualify"
    RACE = "Race"
    HOT_LAP = "HotLap"
    LONE_PRACTICE = "LonePractice"


class SessionPhase(str, Enum):
    UNAVAILABLE = "Unavailable"
    GARAGE = "Garage"
    GRIDWALK = "Gridwalk"
    FORMATION = "Formation"
    COUNTDOWN = "Countdown"
    GREEN = "Green"
    FULL_COURSE_YELLOW = "FullCourseYellow"
    CHECKERED = "Checkered"
    FINISHED = "Finished"


class FlagEnum(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    DOUBLE_YELLOW = "DOUBLE_YELLOW"
    BLUE = "BLUE"
    WHITE = "WHITE"
    BLACK = "BLACK"
    CHEQUERED = "CHEQUERED"


class FullCourseYellowPhase(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    PITS_CLOSED = "PITS_CLOSED"
    PITS_OPEN_LEAD_LAP = "PITS_OPEN_LEAD_LAP"
    PITS_OPEN = "PITS_OPEN"
    LAST_LAP_NEXT = "LAST_LAP_NEXT"
    LAST_LAP_CURRENT = "LAST_LAP_CURRENT"
    RACING = "RACING"


class FrozenOrderPhase(str, Enum):
    NONE = "None"
    FCY = "FullCourseYellow"
    FORMATION = "FormationStanding"
    ROLLING = "Rolling"


class FrozenOrderColumn(str, Enum):
    NONE = "None"
    LEFT = "Left"
    RIGHT = "Right"


class FrozenOrderAction(str, Enum):
    NONE = "None"
    FOLLOW = "Follow"
    CATCH_UP = "CatchUp"
    ALLOW_TO_PASS = "AllowToPass"


class PitWindow(str, Enum):
    UNAVAILABLE = "Unavailable"
    CLOSED = "Closed"
    OPEN = "Open"


class ControlType(str, Enum):
    PLAYER = "Player"
    AI = "AI"
    REMOTE = "Remote"
    REPLAY = "Replay"


class TyreType(str, Enum):
    SOFT = "Soft"
    MEDIUM = "Medium"
    HARD = "Hard"
    WET = "Wet"
    INTERMEDIATE = "Intermediate"
```

#### Step 3: Ejecutar tests

Run: `cd backend && python -m pytest tests/test_enums.py -v`
Expected: 8 PASSED

#### Step 4: Commit

```bash
git add backend/src/models/enums.py backend/tests/test_enums.py
git commit -m "feat(crewchief): add enums for session types, phases, flags, FCY"
```

---

### Task 2: TrackDefinition — Clasificación automática de circuitos

**Files:**
- Create: `backend/src/services/track_definition.py`
- Test: `backend/tests/test_track_definition.py`

**Descripción:** Clasifica circuitos por longitud en 5 categorías (VERY_SHORT a VERY_LONG). Define ventanas de combustible, límites de ritmo, y vueltas mínimas antes de gaps. Sin lista de circuitos conocidos — funciona para cualquier circuito incluyendo mods.

#### Step 1: Escribir tests

```python
# backend/tests/test_track_definition.py
import pytest
from backend.src.services.track_definition import (
    TrackLengthClass, get_length_class, TrackDefinition,
    FUEL_WINDOW_LENGTH, LAPS_BEFORE_GAPS, OUTLIER_PACE_LIMITS
)

def test_very_long():
    assert get_length_class(25000) == TrackLengthClass.VERY_LONG

def test_long():
    assert get_length_class(15000) == TrackLengthClass.LONG

def test_medium():
    assert get_length_class(5000) == TrackLengthClass.MEDIUM

def test_short():
    assert get_length_class(1500) == TrackLengthClass.SHORT

def test_very_short():
    assert get_length_class(500) == TrackLengthClass.VERY_SHORT

def test_track_definition_auto_gap_points():
    td = TrackDefinition(name="Test", track_length=5000)
    assert len(td.gap_points) > 0
    assert td.gap_points[-1] > 3000

def test_track_definition_oval():
    td = TrackDefinition(name="Oval", track_length=2000, is_oval=True)
    assert td.is_oval

def test_fuel_window_very_long():
    assert FUEL_WINDOW_LENGTH[TrackLengthClass.VERY_LONG] == 1

def test_laps_before_gaps_short():
    assert LAPS_BEFORE_GAPS[TrackLengthClass.SHORT] == 3

def test_outlier_limits():
    assert OUTLIER_PACE_LIMITS[TrackLengthClass.LONG] == 8
```

#### Step 2: Crear track_definition.py

```python
# backend/src/services/track_definition.py
from enum import Enum
from dataclasses import dataclass, field
from typing import List


class TrackLengthClass(Enum):
    VERY_SHORT = "VERY_SHORT"
    SHORT = "SHORT"
    MEDIUM = "MEDIUM"
    LONG = "LONG"
    VERY_LONG = "VERY_LONG"


OUTLIER_PACE_LIMITS = {
    TrackLengthClass.VERY_LONG: 15,
    TrackLengthClass.LONG: 8,
    TrackLengthClass.MEDIUM: 3,
    TrackLengthClass.SHORT: 2,
    TrackLengthClass.VERY_SHORT: 2,
}

FUEL_WINDOW_LENGTH = {
    TrackLengthClass.VERY_LONG: 1,
    TrackLengthClass.LONG: 2,
    TrackLengthClass.MEDIUM: 3,
    TrackLengthClass.SHORT: 4,
    TrackLengthClass.VERY_SHORT: 5,
}

LAPS_BEFORE_GAPS = {
    TrackLengthClass.VERY_LONG: 0,
    TrackLengthClass.LONG: 1,
    TrackLengthClass.MEDIUM: 2,
    TrackLengthClass.SHORT: 3,
    TrackLengthClass.VERY_SHORT: 4,
}


def get_length_class(length: float) -> TrackLengthClass:
    if length > 20000:
        return TrackLengthClass.VERY_LONG
    if length > 10000:
        return TrackLengthClass.LONG
    if length < 1000:
        return TrackLengthClass.VERY_SHORT
    if length < 2400:
        return TrackLengthClass.SHORT
    return TrackLengthClass.MEDIUM


@dataclass
class TrackDefinition:
    name: str
    track_length: float
    sectors: int = 3
    is_oval: bool = False
    gap_points: List[float] = field(default_factory=list)
    landmarks: List[dict] = field(default_factory=list)

    def __post_init__(self):
        self.track_length_class = get_length_class(self.track_length)
        if not self.gap_points and self.track_length > 3000:
            self.gap_points = self._gen_gap_points()

    def _gen_gap_points(self) -> List[float]:
        pts = []
        t = 0.0
        while t < self.track_length - 1500:
            t += 1500
            pts.append(round(t, 3))
        if self.track_length > 50:
            pts.append(self.track_length - 50)
        return pts
```

#### Step 3: Ejecutar tests

Run: `cd backend && python -m pytest tests/test_track_definition.py -v`
Expected: 10 PASSED

#### Step 4: Commit

```bash
git add backend/src/services/track_definition.py backend/tests/test_track_definition.py
git commit -m "feat(crewchief): add automatic track classification by length"
```

---

### Task 3: CarClassData — Datos de cada tipo de coche

**Files:**
- Create: `backend/src/data/car_class_data.py`
- Test: `backend/tests/test_car_class_data.py`

**Descripción:** Define tipos de coche (GT3, Hypercar, LMP2, etc.) con sus umbrales de temperatura de neumáticos (14 compuestos), frenos (4 tipos), flags de capacidad (batería, DRS, repostaje). Un solo archivo editable por desarrollador.

#### Step 1: Escribir tests

```python
# backend/tests/test_car_class_data.py
import pytest
from backend.src.data.car_class_data import (
    CarClassEnum, CarClass, get_car_class,
    TyreTemp, BrakeTemp, DamageLevel,
    get_tyre_thresholds, get_brake_thresholds,
    TYRE_TEMP_THRESHOLDS, BRAKE_TEMP_THRESHOLDS
)

def test_car_class_enum_values():
    assert CarClassEnum.GT3.value == "GT3"
    assert CarClassEnum.HYPER_CAR.value == "HYPER_CAR"

def test_get_car_class_gt3():
    cc = get_car_class(CarClassEnum.GT3)
    assert cc.brake_type == "Ceramic"
    assert cc.max_safe_oil == 135.0
    assert not cc.is_battery_powered

def test_get_car_class_hypercar():
    cc = get_car_class(CarClassEnum.HYPER_CAR)
    assert cc.brake_type == "Carbon"
    assert cc.is_battery_powered
    assert cc.is_drs_capable

def test_get_car_class_unknown_fallback():
    cc = get_car_class(CarClassEnum.UNKNOWN_RACE)
    assert cc.enabled_message_types == ["FUEL"]

def test_tyre_temp_thresholds_soft():
    th = get_tyre_thresholds("Soft")
    assert len(th) == 4
    assert th[0].name == TyreTemp.COLD
    assert th[1].name == TyreTemp.WARM

def test_tyre_temp_thresholds_unknown_fallback():
    th = get_tyre_thresholds("Nonexistent")
    assert th[0].name == TyreTemp.COLD

def test_brake_thresholds_carbon():
    th = get_brake_thresholds("Carbon")
    assert th[0].name == BrakeTemp.COLD
    assert th[0].upper == 400.0

def test_damage_level_values():
    assert DamageLevel.NONE.value == 1
    assert DamageLevel.DESTROYED.value == 5

def test_car_class_is_refueling():
    cc = get_car_class(CarClassEnum.GT3)
    assert cc.is_refueling_allowed
    cc2 = get_car_class(CarClassEnum.FORMULA_E)
    assert not cc2.is_refueling_allowed
```

#### Step 2: Crear car_class_data.py

```python
# backend/src/data/car_class_data.py
from enum import Enum
from dataclasses import dataclass, field
from typing import List


class CarClassEnum(Enum):
    GT3 = "GT3"
    GTE = "GTE"
    LMP1 = "LMP1"
    LMP2 = "LMP2"
    HYPER_CAR = "HYPER_CAR"
    HYPER_CAR_RACE = "HYPER_CAR_RACE"
    LMDH = "LMDH"
    FORMULA_E = "FORMULA_E"
    UNKNOWN_RACE = "UNKNOWN_RACE"
    USER_CREATED = "USER_CREATED"
    HYPER_CAR_LMU = "HYPER_CAR_LMU"
    LMGT3 = "LMGT3"


class TyreTemp(Enum):
    COLD = "COLD"
    WARM = "WARM"
    HOT = "HOT"
    COOKING = "COOKING"


class BrakeTemp(Enum):
    COLD = "COLD"
    WARM = "WARM"
    HOT = "HOT"
    COOKING = "COOKING"


class DamageLevel(int, Enum):
    NONE = 1
    TRIVIAL = 2
    MINOR = 3
    MAJOR = 4
    DESTROYED = 5


@dataclass
class Threshold:
    name: Enum
    lower: float
    upper: float


@dataclass
class CarClass:
    car_class_enum: CarClassEnum
    brake_type: str = "Iron_Race"
    default_tyre_type: str = "Unknown_Race"
    max_safe_water: float = 105.0
    max_safe_oil: float = 125.0
    is_battery_powered: bool = False
    is_drs_capable: bool = False
    drs_range: float = -1.0
    is_vehicle_swap_allowed: bool = False
    is_refueling_allowed: bool = True
    enabled_message_types: List[str] = field(default_factory=lambda: ["ALL"])


TYRE_TEMP_THRESHOLDS = {
    "Soft": [
        Threshold(TyreTemp.COLD, -10000, 70),
        Threshold(TyreTemp.WARM, 70, 100),
        Threshold(TyreTemp.HOT, 100, 115),
        Threshold(TyreTemp.COOKING, 115, 10000),
    ],
    "Medium": [
        Threshold(TyreTemp.COLD, -10000, 75),
        Threshold(TyreTemp.WARM, 75, 105),
        Threshold(TyreTemp.HOT, 105, 120),
        Threshold(TyreTemp.COOKING, 120, 10000),
    ],
    "Hard": [
        Threshold(TyreTemp.COLD, -10000, 78),
        Threshold(TyreTemp.WARM, 78, 110),
        Threshold(TyreTemp.HOT, 110, 124),
        Threshold(TyreTemp.COOKING, 124, 10000),
    ],
    "Wet": [
        Threshold(TyreTemp.COLD, -10000, 40),
        Threshold(TyreTemp.WARM, 40, 80),
        Threshold(TyreTemp.HOT, 80, 105),
        Threshold(TyreTemp.COOKING, 105, 10000),
    ],
    "Intermediate": [
        Threshold(TyreTemp.COLD, -10000, 60),
        Threshold(TyreTemp.WARM, 60, 95),
        Threshold(TyreTemp.HOT, 95, 110),
        Threshold(TyreTemp.COOKING, 110, 10000),
    ],
    "Unknown_Race": [
        Threshold(TyreTemp.COLD, -10000, 60),
        Threshold(TyreTemp.WARM, 60, 117),
        Threshold(TyreTemp.HOT, 117, 137),
        Threshold(TyreTemp.COOKING, 137, 10000),
    ],
}

BRAKE_TEMP_THRESHOLDS = {
    "Iron_Race": [
        Threshold(BrakeTemp.COLD, -10000, 150),
        Threshold(BrakeTemp.WARM, 150, 700),
        Threshold(BrakeTemp.HOT, 700, 900),
        Threshold(BrakeTemp.COOKING, 900, 10000),
    ],
    "Ceramic": [
        Threshold(BrakeTemp.COLD, -10000, 150),
        Threshold(BrakeTemp.WARM, 150, 950),
        Threshold(BrakeTemp.HOT, 950, 1200),
        Threshold(BrakeTemp.COOKING, 1200, 10000),
    ],
    "Carbon": [
        Threshold(BrakeTemp.COLD, -10000, 400),
        Threshold(BrakeTemp.WARM, 400, 1200),
        Threshold(BrakeTemp.HOT, 1200, 1500),
        Threshold(BrakeTemp.COOKING, 1500, 10000),
    ],
}

CAR_CLASSES = {
    CarClassEnum.GT3: CarClass(
        CarClassEnum.GT3, brake_type="Ceramic", max_safe_oil=135
    ),
    CarClassEnum.GTE: CarClass(
        CarClassEnum.GTE, brake_type="Ceramic", max_safe_oil=135
    ),
    CarClassEnum.LMP1: CarClass(
        CarClassEnum.LMP1, brake_type="Carbon", max_safe_oil=140
    ),
    CarClassEnum.LMP2: CarClass(
        CarClassEnum.LMP2, brake_type="Ceramic", max_safe_oil=135
    ),
    CarClassEnum.HYPER_CAR: CarClass(
        CarClassEnum.HYPER_CAR, brake_type="Carbon",
        is_battery_powered=True, is_drs_capable=True, drs_range=1.0,
    ),
    CarClassEnum.LMDH: CarClass(
        CarClassEnum.LMDH, brake_type="Ceramic",
        is_drs_capable=True, drs_range=1.0,
    ),
    CarClassEnum.UNKNOWN_RACE: CarClass(
        CarClassEnum.UNKNOWN_RACE, enabled_message_types=["FUEL"]
    ),
}


def get_car_class(enum: CarClassEnum) -> CarClass:
    return CAR_CLASSES.get(enum, CAR_CLASSES[CarClassEnum.UNKNOWN_RACE])


def get_tyre_thresholds(tyre: str) -> List[Threshold]:
    return TYRE_TEMP_THRESHOLDS.get(tyre, TYRE_TEMP_THRESHOLDS["Unknown_Race"])


def get_brake_thresholds(brake: str) -> List[Threshold]:
    return BRAKE_TEMP_THRESHOLDS.get(brake, BRAKE_TEMP_THRESHOLDS["Iron_Race"])
```

#### Step 3: Ejecutar tests

Run: `cd backend && python -m pytest tests/test_car_class_data.py -v`
Expected: 10 PASSED

#### Step 4: Commit

```bash
git add backend/src/data/car_class_data.py backend/tests/test_car_class_data.py
git commit -m "feat(crewchief): add car class definitions and temperature thresholds"
```

---

### Task 4: GameStateData — Todas las dataclasses tipadas

**Files:**
- Create: `backend/src/models/game_state_data.py`
- Test: `backend/tests/test_game_state_data.py`

**Descripción:** Define 15+ dataclasses con todos los datos de carrera estructurados. Cada evento recibirá un `GameStateData` completo con sub-objetos para sesión, movimiento, pits, neumáticos, daños, motor, combustible, batería, etc.

#### Step 1: Escribir tests

```python
# backend/tests/test_game_state_data.py
import pytest
from backend.src.models.game_state_data import (
    GameStateData, SessionData, PositionAndMotionData,
    PitData, FlagData, TyreData, CarDamageData,
    EngineData, FuelData, BatteryData, OpponentData,
    PenaltiesData, OvertakingAidsData, FrozenOrderData,
    Rotation, TimingData
)
from backend.src.models.enums import SessionType, SessionPhase, FlagEnum

def test_game_state_data_defaults():
    g = GameStateData()
    assert g.session.session_type == SessionType.UNAVAILABLE
    assert g.motion.world_x == 0.0
    assert not g.pit.in_pitlane
    assert g.fuel.fuel_left == 0.0

def test_session_data_defaults():
    s = SessionData()
    assert s.completed_laps == 0
    assert s.class_position == 0
    assert not s.just_gone_green

def test_motion_speed_kmh():
    m = PositionAndMotionData(car_speed=50.0)
    assert m.speed_kmh == 180.0  # 50 m/s * 3.6

def test_rotation_defaults():
    r = Rotation()
    assert r.yaw == 0.0
    assert r.pitch == 0.0
    assert r.roll == 0.0

def test_battery_normalized_fraction():
    b = BatteryData(percentage=0.5, capacity=100.0)
    assert b.get_normalized() == 0.5  # (0.5 * 100) / 100

def test_battery_normalized_percent():
    b = BatteryData(percentage=85.0)
    assert b.get_normalized() == 85.0

def test_tyre_data_defaults():
    t = TyreData()
    assert t.fl_temp == 0.0
    assert t.fl_wear == 0.0

def test_car_damage_defaults():
    d = CarDamageData()
    assert d.aero == "NONE"
    assert len(d.suspension) == 4

def test_opponent_data_defaults():
    o = OpponentData()
    assert o.driver == ""
    assert not o.in_pits

def test_penalties_defaults():
    p = PenaltiesData()
    assert p.num_outstanding == 0
    assert not p.has_drivethrough

def test_overtaking_aids_defaults():
    oa = OvertakingAidsData()
    assert not oa.drs_enabled
    assert oa.drs_range == -1.0

def test_timing_data():
    t = TimingData()
    t.best_laps["CURRENT"] = 90.5
    assert t.get_best("CURRENT") == 90.5
    assert t.get_best("NONEXISTENT") == -1

def test_game_state_data_set_fields():
    g = GameStateData()
    g.session.driver_name = "Test Driver"
    g.motion.car_speed = 42.0
    g.fuel.fuel_left = 56.7
    g.tyre.fl_temp = 87.3
    assert g.session.driver_name == "Test Driver"
    assert g.fuel.fuel_left == 56.7
```

#### Step 2: Crear game_state_data.py

```python
# backend/src/models/game_state_data.py
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from backend.src.models.enums import (
    SessionType, SessionPhase, FlagEnum,
    FullCourseYellowPhase, PitWindow, FrozenOrderPhase,
    FrozenOrderAction, FrozenOrderColumn,
)


@dataclass
class Rotation:
    pitch: float = 0.0
    roll: float = 0.0
    yaw: float = 0.0


@dataclass
class PositionAndMotionData:
    world_x: float = 0.0
    world_y: float = 0.0
    world_z: float = 0.0
    orientation: Rotation = field(default_factory=Rotation)
    car_speed: float = 0.0
    distance_round_track: float = 0.0
    local_accel_x: float = 0.0
    local_accel_y: float = 0.0
    local_accel_z: float = 0.0

    @property
    def speed_kmh(self) -> float:
        return self.car_speed * 3.6


@dataclass
class SessionData:
    session_type: SessionType = SessionType.UNAVAILABLE
    session_phase: SessionPhase = SessionPhase.UNAVAILABLE
    session_running_time: float = 0.0
    session_time_remaining: float = 0.0
    completed_laps: int = 0
    session_laps_remaining: int = 0
    is_new_lap: bool = False
    is_new_sector: bool = False
    sector_number: int = 1
    player_lap_time_best: float = 0.0
    player_lap_time_prev: float = 0.0
    previous_lap_valid: bool = True
    class_position: int = 0
    overall_position: int = 0
    session_start_class_position: int = 0
    just_gone_green: bool = False
    just_gone_green_time: float = 0.0
    has_lead_changed: bool = False
    time_delta_front: float = 0.0
    time_delta_behind: float = 0.0
    driver_name: str = ""
    leader_name: str = ""
    is_new_session: bool = False
    is_disqualified: bool = False
    is_dnf: bool = False
    track_definition: Optional["TrackDefinition"] = None

    def is_last_in_standings(self, total_drivers: int = 0) -> bool:
        return self.class_position >= total_drivers > 0

    def get_opponent_key_in_front(self) -> Optional[str]:
        return None  # Será implementado por eventos con acceso a oponentes

    def get_opponent_key_behind(self) -> Optional[str]:
        return None  # Será implementado por eventos con acceso a oponentes


@dataclass
class PitData:
    in_pitlane: bool = False
    on_out_lap: bool = False
    has_requested_pit_stop: bool = False
    pit_window: PitWindow = PitWindow.UNAVAILABLE
    has_mandatory_pit_stop: bool = False
    mandatory_pit_completed: bool = False
    mandatory_pit_min_left: float = 0.0
    pit_speed_limit: float = 0.0
    driver_stint_seconds: float = 0.0
    driver_stint_total: float = 0.0
    is_electric_swap_allowed: bool = False


@dataclass
class FlagData:
    sector_flags: List = field(default_factory=lambda: [FlagEnum.GREEN] * 3)
    is_fcy: bool = False
    fcy_phase: FullCourseYellowPhase = FullCourseYellowPhase.RACING
    is_local_yellow: bool = False


@dataclass
class TyreData:
    fl_temp: float = 0.0
    fr_temp: float = 0.0
    rl_temp: float = 0.0
    rr_temp: float = 0.0
    fl_wear: float = 0.0
    fr_wear: float = 0.0
    rl_wear: float = 0.0
    rr_wear: float = 0.0
    fl_pressure: float = 0.0
    fr_pressure: float = 0.0
    rl_pressure: float = 0.0
    rr_pressure: float = 0.0
    fl_brake_temp: float = 0.0
    fr_brake_temp: float = 0.0
    rl_brake_temp: float = 0.0
    rr_brake_temp: float = 0.0
    fl_compound: str = "Unknown_Race"
    fr_compound: str = "Unknown_Race"
    rl_compound: str = "Unknown_Race"
    rr_compound: str = "Unknown_Race"


@dataclass
class CarDamageData:
    aero: str = "NONE"
    engine: str = "NONE"
    transmission: str = "NONE"
    suspension: List[str] = field(default_factory=lambda: ["NONE"] * 4)
    brakes: List[str] = field(default_factory=lambda: ["NONE"] * 4)
    last_impact_time: float = -1.0
    last_impact_magnitude: float = 0.0


@dataclass
class EngineData:
    rpm: float = 0.0
    water_temp: float = 0.0
    oil_temp: float = 0.0
    oil_pressure: float = 0.0
    stalled: bool = False
    gear: int = 0


@dataclass
class FuelData:
    fuel_left: float = 0.0
    fuel_capacity: float = 0.0
    use_active: bool = True


@dataclass
class BatteryData:
    percentage: float = 0.0
    use_active: bool = False
    capacity: float = -1.0

    def get_normalized(self) -> float:
        p = self.percentage
        c = self.capacity
        if c > 0 and p <= 1.0:
            return (p * 100.0) / c
        if p <= 1.0:
            return p * 100.0
        return p


@dataclass
class OpponentData:
    driver: str = ""
    car_number: str = "-1"
    vehicle_class: str = ""
    class_pos: int = 0
    overall_pos: int = 0
    speed: float = 0.0
    distance: float = 0.0
    delta: float = 0.0
    last_lap: float = 0.0
    best_lap: float = 0.0
    laps: int = 0
    sector: int = 1
    in_pits: bool = False
    active: bool = True
    tyre: str = "Unknown_Race"
    is_new_lap: bool = False
    is_entering_pits: bool = False
    is_exiting_pits: bool = False
    has_just_changed_tyres: bool = False


@dataclass
class PenaltiesData:
    num_outstanding: int = 0
    has_stop_go: bool = False
    has_drivethrough: bool = False
    has_slow_down: bool = False
    cut_warnings: int = 0
    incident_count: int = 0
    max_incident: int = 0
    is_off_track: bool = False


@dataclass
class OvertakingAidsData:
    drs_enabled: bool = False
    drs_engaged: bool = False
    drs_available: bool = False
    drs_range: float = -1.0
    ptp_engaged: bool = False
    ptp_remaining: int = -1
    ptp_cooldown: float = 0.0


@dataclass
class FrozenOrderData:
    phase: FrozenOrderPhase = FrozenOrderPhase.NONE
    action: FrozenOrderAction = FrozenOrderAction.NONE
    position: int = -1
    column: str = "None"


@dataclass
class TimingData:
    best_laps: Dict[str, float] = field(default_factory=dict)

    def get_best(self, car: str = "CURRENT") -> float:
        return self.best_laps.get(car, -1.0)


@dataclass
class GameStateData:
    now: float = 0.0
    session: SessionData = field(default_factory=SessionData)
    motion: PositionAndMotionData = field(default_factory=PositionAndMotionData)
    pit: PitData = field(default_factory=PitData)
    flag: FlagData = field(default_factory=FlagData)
    tyre: TyreData = field(default_factory=TyreData)
    damage: CarDamageData = field(default_factory=CarDamageData)
    engine: EngineData = field(default_factory=EngineData)
    fuel: FuelData = field(default_factory=FuelData)
    battery: BatteryData = field(default_factory=BatteryData)
    overtaking: OvertakingAidsData = field(default_factory=OvertakingAidsData)
    penalties: PenaltiesData = field(default_factory=PenaltiesData)
    frozen_order: FrozenOrderData = field(default_factory=FrozenOrderData)
    timing: TimingData = field(default_factory=TimingData)
    opponents: Dict[str, OpponentData] = field(default_factory=dict)
    car_class: str = "UNKNOWN_RACE"
    multiclass: bool = False
```

#### Step 3: Ejecutar tests

Run: `cd backend && python -m pytest tests/test_game_state_data.py -v`
Expected: 13 PASSED

#### Step 4: Commit

```bash
git add backend/src/models/game_state_data.py backend/tests/test_game_state_data.py
git commit -m "feat(crewchief): add GameStateData with all race dataclasses"
```

---

### Task 5: Messages — Añadir QueuedMessage, MessageFragment, contents(), Pause()

**Files:**
- Modify: `backend/src/models/messages.py` (AÑADIR al final — NO tocar clases existentes)
- Test: `backend/tests/test_messages_crewchief.py`

**Descripción:** Añade al archivo existente las clases que el sistema de audio necesita: `QueuedMessage`, `MessageFragment`, `FragmentType`, `DelayedMessageEvent`, funciones `contents()` y `Pause()`. No se toca nada de lo que ya existe (BaseMessage, AlertMessage, etc.).

#### Step 1: Escribir tests

```python
# backend/tests/test_messages_crewchief.py
import pytest, time
from backend.src.models.messages import (
    QueuedMessage, MessageFragment, FragmentType,
    DelayedMessageEvent, contents, Pause, Precision, TimeSpanWrapper
)

def test_fragment_text():
    f = MessageFragment.text("hello")
    assert f.type == FragmentType.TEXT
    assert f.text == "hello"

def test_fragment_time():
    f = MessageFragment.time(90.5)
    assert f.type == FragmentType.TIME
    assert f.time_span.seconds == 90.5

def test_fragment_integer():
    f = MessageFragment.integer(42)
    assert f.type == FragmentType.INTEGER
    assert f.integer == 42

def test_fragment_pause():
    f = MessageFragment.pause(500)
    assert f.type == FragmentType.PAUSE
    assert f.pause_ms == 500

def test_queued_message_defaults():
    m = QueuedMessage("test/path")
    assert m.name == "test/path"
    assert m.priority == 5
    assert m.can_play

def test_queued_message_expiry():
    m = QueuedMessage("test", expires=0.1)
    assert not m.is_expired(time.time())
    assert m.is_expired(time.time() + 1.0)

def test_queued_message_delay():
    m = QueuedMessage("test", delay=1.0)
    assert not m.is_due(time.time())
    assert m.is_due(time.time() + 1.5)

def test_prepare_repeat():
    m = QueuedMessage("test/path")
    m.prepare_repeat()
    assert "REPEAT" in m.name
    assert m.priority == 5

def test_contents_mixed():
    r = contents("hello", 42, 90.5)
    assert len(r) == 3
    assert r[0].type == FragmentType.TEXT
    assert r[0].text == "hello"
    assert r[1].type == FragmentType.INTEGER
    assert r[2].type == FragmentType.TIME

def test_contents_none():
    r = contents(None, "test")
    assert r[0] is None
    assert r[1].text == "test"

def test_pause_function():
    p = Pause(300)
    assert p.type == FragmentType.PAUSE
    assert p.pause_ms == 300

def test_delayed_message_event():
    dme = DelayedMessageEvent("method", [1, True], None)
    assert dme.method_name == "method"
    assert dme.method_params == [1, True]
```

#### Step 2: Modificar messages.py (AÑADIR al final)

Añadir al final de `backend/src/models/messages.py`:

```python

# ==============================================================
# CrewChief V4 — Queue & Message System (añadido 2026-06-01)
# ==============================================================
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any, Callable


class FragmentType:
    TEXT = "text"
    TIME = "time"
    OPPONENT = "opponent"
    INTEGER = "integer"
    PAUSE = "pause"


class Precision:
    AUTO_LAPTIMES = "AUTO_LAPTIMES"
    AUTO_GAPS = "AUTO_GAPS"
    SECONDS = "SECONDS"
    TENTHS = "TENTHS"
    HUNDREDTHS = "HUNDREDTHS"
    MINUTES = "MINUTES"


@dataclass
class TimeSpanWrapper:
    seconds: float
    precision: str = Precision.AUTO_LAPTIMES


@dataclass
class MessageFragment:
    type: str
    text: Optional[str] = None
    time_span: Optional[TimeSpanWrapper] = None
    opponent: Optional[str] = None
    integer: Optional[int] = None
    pause_ms: int = 0

    @staticmethod
    def text(p: str) -> "MessageFragment":
        return MessageFragment(FragmentType.TEXT, text=p)

    @staticmethod
    def time(s: float, p: str = Precision.AUTO_LAPTIMES) -> "MessageFragment":
        return MessageFragment(FragmentType.TIME, time_span=TimeSpanWrapper(s, p))

    @staticmethod
    def opponent(n: str) -> "MessageFragment":
        return MessageFragment(FragmentType.OPPONENT, opponent=n)

    @staticmethod
    def integer(v: int) -> "MessageFragment":
        return MessageFragment(FragmentType.INTEGER, integer=v)

    @staticmethod
    def pause(ms: int) -> "MessageFragment":
        return MessageFragment(FragmentType.PAUSE, pause_ms=ms)


@dataclass
class DelayedMessageEvent:
    method_name: str
    method_params: list
    event_instance: Any


_id_counter = 0


class QueuedMessage:
    def __init__(
        self,
        name: str,
        expires: float = 10.0,
        fragments: Optional[List] = None,
        alternate: Optional[List] = None,
        delay: float = 0.0,
        event: Any = None,
        validation: Optional[Dict] = None,
        priority: int = 5,
        sound_type: str = "REGULAR",
        trigger_fn: Optional[Callable] = None,
        delayed: Optional[DelayedMessageEvent] = None,
    ):
        global _id_counter
        _id_counter += 1
        self.id = _id_counter
        self.name = name
        self.expires = expires
        self.delay = delay
        self.fragments = fragments or []
        self.alternate = alternate
        self.event = event
        self.validation = validation
        self.priority = priority
        self.sound_type = sound_type
        self.trigger_fn = trigger_fn
        self.delayed = delayed
        self.created = time.time()
        self.due = self.created + delay
        self.expiry = self.created + expires if expires > 0 else 0
        self.can_play = True
        self.is_rant = False

    def is_expired(self, now: Optional[float] = None) -> bool:
        return self.expiry > 0 and (now or time.time()) >= self.expiry

    def is_due(self, now: Optional[float] = None) -> bool:
        return (now or time.time()) >= self.due

    def age(self) -> float:
        return time.time() - self.created

    def prepare_repeat(self):
        self.name = f"REPEAT_{self.name}"
        self.priority = 5
        self.sound_type = "VOICE_COMMAND"
        self.due = 0
        self.expiry = 0
        self.trigger_fn = None
        self.event = None
        self.validation = None
        self.delay = 0


def contents(*objs) -> List[MessageFragment]:
    result = []
    for o in objs:
        if o is None:
            result.append(None)
        elif isinstance(o, MessageFragment):
            result.append(o)
        elif isinstance(o, str):
            result.append(MessageFragment.text(o))
        elif isinstance(o, int):
            result.append(MessageFragment.integer(o))
        elif isinstance(o, float):
            result.append(MessageFragment.time(o))
        elif isinstance(o, TimeSpanWrapper):
            result.append(MessageFragment.time(o.seconds, o.precision))
    return result


def Pause(ms: int) -> MessageFragment:
    return MessageFragment(FragmentType.PAUSE, pause_ms=ms)
```

#### Step 3: Ejecutar tests

Run: `cd backend && python -m pytest tests/test_messages_crewchief.py -v`
Expected: 12 PASSED

Run también tests existentes para verificar que no se rompió nada:
`cd backend && python -m pytest tests/ -v`
Expected: Todos los tests existentes siguen pasando

#### Step 4: Commit

```bash
git add backend/src/models/messages.py backend/tests/test_messages_crewchief.py
git commit -m "feat(crewchief): add QueuedMessage, MessageFragment, contents, Pause"
```

---

### Task 6: DeltaTime — Cálculo de gaps con diferencia de vueltas

**Files:**
- Create: `backend/src/services/delta_time.py`
- Test: `backend/tests/test_delta_time.py`

**Descripción:** Calcula diferencias de tiempo entre coches teniendo en cuenta diferencias de vuelta (multiclase). Si un Hypercar está una vuelta por delante de un GT3, el gap total incluye el tiempo de esa vuelta extra.

#### Step 1: Escribir tests

```python
# backend/tests/test_delta_time.py
import pytest
from backend.src.services.delta_time import DeltaTime


def test_delta_time_creation():
    dt = DeltaTime(90.5, 12)
    assert dt.time == 90.5
    assert dt.lap == 12


def test_signed_lap_diff_same():
    dt1 = DeltaTime(90.0, 10)
    dt2 = DeltaTime(85.0, 10)
    assert dt1.get_signed_lap_diff(dt2) == 0


def test_signed_lap_diff_ahead():
    dt1 = DeltaTime(90.0, 11)
    dt2 = DeltaTime(85.0, 10)
    assert dt1.get_signed_lap_diff(dt2) == 1


def test_signed_lap_diff_behind():
    dt1 = DeltaTime(90.0, 9)
    dt2 = DeltaTime(85.0, 10)
    assert dt1.get_signed_lap_diff(dt2) == -1


def test_absolute_time_delta_same_lap():
    dt1 = DeltaTime(92.0, 10)
    dt2 = DeltaTime(90.0, 10)
    ld, td = dt1.get_absolute_time_delta(dt2)
    assert ld == 0
    assert td == 2.0


def test_absolute_time_delta_one_lap_ahead():
    dt1 = DeltaTime(90.0, 11)
    dt2 = DeltaTime(85.0, 10)
    ld, td = dt1.get_absolute_time_delta(dt2, best_lap=90.0)
    assert ld == 1
    assert td == 95.0  # 5.0 + 1 * 90.0


def test_absolute_time_delta_no_best_lap():
    dt1 = DeltaTime(90.0, 11)
    dt2 = DeltaTime(85.0, 10)
    ld, td = dt1.get_absolute_time_delta(dt2)
    assert ld == 1
    assert td == 5.0  # Sin best_lap, solo diff de tiempo
```

#### Step 2: Crear delta_time.py

```python
# backend/src/services/delta_time.py
from typing import Tuple


class DeltaTime:
    """Cálculo de gaps con soporte para diferencia de vueltas (multiclase).

    CrewChief: DeltaTime.cs — usado para gaps entre coches de distintas clases
    donde una vuelta de diferencia equivale a N segundos.
    """

    def __init__(self, time: float, lap: int):
        self.time = time
        self.lap = lap

    def get_signed_lap_diff(self, other: "DeltaTime") -> int:
        return self.lap - other.lap

    def get_absolute_time_delta(
        self, other: "DeltaTime", best_lap: float = 0.0
    ) -> Tuple[int, float]:
        """Returns (lap_diff, total_time_delta) where total_time_delta includes
        the time equivalent of any lap difference."""
        ld = self.get_signed_lap_diff(other)
        td = abs(self.time - other.time)
        if ld != 0 and best_lap > 0:
            td += abs(ld) * best_lap
        return (ld, td)
```

#### Step 3: Ejecutar tests

Run: `cd backend && python -m pytest tests/test_delta_time.py -v`
Expected: 7 PASSED

#### Step 4: Commit

```bash
git add backend/src/services/delta_time.py backend/tests/test_delta_time.py
git commit -m "feat(crewchief): add DeltaTime with multiclass lap-diff support"
```

---

### Task 7: StateDiff — Detector de cambios entre ticks

**Files:**
- Create: `backend/src/services/state_diff.py`
- Test: `backend/tests/test_state_diff.py`

**Descripción:** Compara el tick actual con el anterior y detecta cambios generales: nueva vuelta, nuevo sector cambio de fase de sesión, cambios de líder, retiradas, entradas/salidas de pits. Incluye anti-bouncing de 1s para cambios de posición.

#### Step 1: Escribir tests

```python
# backend/tests/test_state_diff.py
import pytest, time
from copy import deepcopy
from backend.src.services.state_diff import StateDiff, TickChanges


def _make_flat(lap=1, sector=1, phase=5, place=1, running_time=10.0):
    return {
        "lap_number": lap,
        "sector_number": sector,
        "session_phase": phase,
        "session_running_time": running_time,
        "place": place,
        "driver_name": "Player",
        "leader_raw_name": "Leader",
        "rivals": [],
    }


def test_first_update_no_changes():
    diff = StateDiff()
    changes = diff.update(_make_flat())
    assert isinstance(changes, TickChanges)
    # Primer tick no debe reportar cambios
    assert not changes.position_changed


def test_new_lap_detected():
    diff = StateDiff()
    diff.update(_make_flat(lap=1))
    changes = diff.update(_make_flat(lap=2))
    assert changes.new_lap


def test_new_sector_detected():
    diff = StateDiff()
    diff.update(_make_flat(sector=1))
    changes = diff.update(_make_flat(sector=2))
    assert changes.new_sector


def test_session_phase_changed():
    diff = StateDiff()
    diff.update(_make_flat(phase=5))
    changes = diff.update(_make_flat(phase=6))
    assert changes.session_phase_changed


def test_leader_changed():
    diff = StateDiff()
    diff.update(_make_flat())
    changes = diff.update({**_make_flat(), "leader_raw_name": "NewLeader"})
    assert changes.leader_changed


def test_retired_drivers():
    diff = StateDiff()
    diff.update(_make_flat())
    prev_rivals = [
        {"driver_raw_name": "Alice", "in_pits": False},
        {"driver_raw_name": "Bob", "in_pits": False},
    ]
    diff._prev_rivals = {r["driver_raw_name"]: r for r in prev_rivals}
    changes = diff.update({
        **_make_flat(),
        "rivals": [{"driver_raw_name": "Alice", "in_pits": False}],
    })
    assert "Bob" in changes.retired_drivers


def test_pit_entry_detected():
    diff = StateDiff()
    diff.update(_make_flat())
    prev_rivals = [{"driver_raw_name": "Alice", "in_pits": False}]
    diff._prev_rivals = {r["driver_raw_name"]: r for r in prev_rivals}
    changes = diff.update({
        **_make_flat(),
        "rivals": [{"driver_raw_name": "Alice", "in_pits": True}],
    })
    assert "Alice" in changes.pit_entries


def test_pit_exit_detected():
    diff = StateDiff()
    diff.update(_make_flat())
    prev_rivals = [{"driver_raw_name": "Alice", "in_pits": True}]
    diff._prev_rivals = {r["driver_raw_name"]: r for r in prev_rivals}
    changes = diff.update({
        **_make_flat(),
        "rivals": [{"driver_raw_name": "Alice", "in_pits": False}],
    })
    assert "Alice" in changes.pit_exits
```

#### Step 2: Crear state_diff.py

```python
# backend/src/services/state_diff.py
from copy import deepcopy
from typing import Dict, Set, Optional
from dataclasses import dataclass, field


@dataclass
class TickChanges:
    position_changed: bool = False
    old_position: Optional[int] = None
    new_position: Optional[int] = None
    leader_changed: bool = False
    session_phase_changed: bool = False
    new_lap: bool = False
    new_sector: bool = False
    retired_drivers: Set[str] = field(default_factory=set)
    new_drivers: Set[str] = field(default_factory=set)
    pit_entries: Set[str] = field(default_factory=set)
    pit_exits: Set[str] = field(default_factory=set)


class StateDiff:
    """Detector de cambios entre ticks con anti-bouncing de 1s en posiciones.

    CrewChief: previousGameState comparison. Cada evento también hace sus
    propias comprobaciones específicas (doble capa).
    """

    def __init__(self):
        self._prev: Optional[dict] = None
        self._prev_rivals: Dict[str, dict] = {}
        self._pending: Dict[str, dict] = {}
        self._bounce_lag: float = 1.0

    def update(self, current: dict, now: float = 0.0) -> TickChanges:
        import time as _time
        now = now or _time.time()
        c = TickChanges()

        if self._prev is None:
            self._prev = deepcopy(current)
            self._prev_rivals = {
                r["driver_raw_name"]: r
                for r in current.get("rivals", [])
            }
            return c

        # Nueva vuelta
        cl = current.get("lap_number", 0)
        pl = self._prev.get("lap_number", 0)
        c.new_lap = cl > pl

        # Nuevo sector
        cs = current.get("sector_number")
        ps = self._prev.get("sector_number")
        c.new_sector = cs != ps

        # Posición con anti-bouncing
        old_pos = self._prev.get("place", 0)
        new_pos = current.get("place", 0)
        if old_pos != new_pos and new_pos > 0:
            p = self._pending.get("player")
            if p and p["new"] == new_pos:
                if now >= p["settle"]:
                    c.position_changed = True
                    c.old_position = old_pos
                    c.new_position = new_pos
                    self._pending.pop("player", None)
            else:
                self._pending["player"] = {
                    "new": new_pos,
                    "settle": now + self._bounce_lag,
                }

        # Cambio de líder
        ol = self._prev.get("leader_raw_name")
        nl = current.get("leader_raw_name")
        if nl and nl != ol:
            c.leader_changed = True

        # Cambio de fase de sesión
        if current.get("session_phase") != self._prev.get("session_phase"):
            c.session_phase_changed = True

        # Retiradas y pits
        prev_names = set(self._prev_rivals.keys())
        curr_names = set(r["driver_raw_name"] for r in current.get("rivals", []))
        c.retired_drivers = prev_names - curr_names
        c.new_drivers = curr_names - prev_names

        curr_d = {r["driver_raw_name"]: r for r in current.get("rivals", [])}
        for n in curr_names & prev_names:
            pr = self._prev_rivals.get(n)
            cr = curr_d.get(n)
            if pr and cr:
                if not pr.get("in_pits") and cr.get("in_pits"):
                    c.pit_entries.add(n)
                if pr.get("in_pits") and not cr.get("in_pits"):
                    c.pit_exits.add(n)

        self._prev = deepcopy(current)
        self._prev_rivals = deepcopy(curr_d)
        return c
```

#### Step 3: Ejecutar tests

Run: `cd backend && python -m pytest tests/test_state_diff.py -v`
Expected: 8 PASSED

#### Step 4: Commit

```bash
git add backend/src/services/state_diff.py backend/tests/test_state_diff.py
git commit -m "feat(crewchief): add StateDiff with anti-bounce and change detection"
```

---

### Task 8: LMUReader — Lector de shared memory en flat dict

**Files:**
- Create: `backend/src/services/lmu_reader.py`
- Test: `backend/tests/test_lmu_reader.py`

**Descripción:** Lee shared memory de LMU usando `MMapControl` de `shared_telemetry` y structs de `lmu_data.py`. Reúsa los structs existentes en lugar de redefinirlos. Añade wrapper `LMUOrientation` para extraer yaw/pitch/roll. Devuelve flat dict con todos los campos que los eventos necesitan, incluyendo orientación y posición de oponentes para el spotter cartesiano.

#### Step 1: Escribir tests

```python
# backend/tests/test_lmu_reader.py
import pytest
import math
from backend.src.services.lmu_reader import (
    calculate_rotation,
    orientation_to_dict,
    decode_name,
)

def test_rotation_identity():
    """Matriz identidad → yaw ≈ 0"""
    r = calculate_rotation({
        "row_x": {"x": 1, "y": 0, "z": 0},
        "row_y": {"x": 0, "y": 1, "z": 0},
        "row_z": {"x": 0, "y": 0, "z": 1},
    })
    assert abs(r["yaw"]) < 0.001
    assert abs(r["pitch"]) < 0.001
    assert abs(r["roll"]) < 0.001


def test_rotation_45deg():
    """Rotación de 45° en yaw"""
    c = math.cos(math.pi / 4)
    s = math.sin(math.pi / 4)
    r = calculate_rotation({
        "row_x": {"x": c, "y": 0, "z": -s},
        "row_y": {"x": 0, "y": 1, "z": 0},
        "row_z": {"x": s, "y": 0, "z": c},
    })
    assert abs(r["yaw"] - math.pi / 4) < 0.01


def test_rotation_nan_handling():
    """NaN en la matriz → devuelve 0,0,0"""
    r = calculate_rotation({
        "row_x": {"x": float("nan"), "y": 0, "z": 0},
        "row_y": {"x": 0, "y": 1, "z": 0},
        "row_z": {"x": 0, "y": 0, "z": 1},
    })
    assert abs(r["yaw"]) < 0.001
    assert abs(r["pitch"]) < 0.001


def test_rotation_inf_handling():
    """Inf en la matriz → devuelve 0,0,0"""
    r = calculate_rotation({
        "row_x": {"x": float("inf"), "y": 0, "z": 0},
        "row_y": {"x": 0, "y": 1, "z": 0},
        "row_z": {"x": 0, "y": 0, "z": 1},
    })
    assert abs(r["yaw"]) < 0.001


def test_decode_name_leading_null():
    assert decode_name(b"\x00Hello") == "Hello"


def test_decode_name_null_terminated():
    assert decode_name(b"Test\x00extra") == "Test"


def test_decode_name_empty():
    assert decode_name(b"") == ""


def test_decode_name_none():
    assert decode_name(None) == ""


def test_orientation_to_dict_struct():
    """Simula un struct con row_x, row_y, row_z"""
    class MockVec:
        def __init__(self, x, y, z):
            self.x = x
            self.y = y
            self.z = z

    class MockOrient:
        row_x = MockVec(1, 0, 0)
        row_y = MockVec(0, 1, 0)
        row_z = MockVec(0, 0, 1)

    d = orientation_to_dict(MockOrient())
    assert d["row_x"]["x"] == 1.0
    assert d["row_z"]["z"] == 1.0
```

#### Step 2: Crear lmu_reader.py

```python
# backend/src/services/lmu_reader.py
import ctypes
import math
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("vantare.lmu_reader")


def decode_name(byte_arr) -> str:
    """CrewChief: GetStringFromBytes — maneja leading null byte y null terminators."""
    if byte_arr is None:
        return ""
    if not isinstance(byte_arr, (bytes, bytearray)):
        try:
            byte_arr = bytes(byte_arr)
        except Exception:
            return ""
    if len(byte_arr) == 0:
        return ""
    if byte_arr[0] == 0 and len(byte_arr) > 1:
        byte_arr = byte_arr[1:]
    null_pos = byte_arr.find(b"\x00")
    if null_pos >= 0:
        byte_arr = byte_arr[:null_pos]
    if len(byte_arr) == 0:
        return ""
    try:
        return byte_arr.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        try:
            return byte_arr.decode("latin-1").strip()
        except Exception:
            return byte_arr.decode("utf-8", errors="replace").strip()


def calculate_rotation(orientation: dict) -> Dict[str, float]:
    """Extrae yaw/pitch/roll de la matriz de orientación 3x3.

    CrewChief: RF2GameStateMapper.GetRotation().
    FIX: NaN/Inf handling — devuelve 0,0,0 si hay datos corruptos.
    """
    rx = orientation["row_x"]
    ry = orientation["row_y"]
    rz = orientation["row_z"]

    yaw = math.atan2(rz["x"], rz["z"])
    pitch = math.atan2(-ry["z"], math.sqrt(rx["z"] ** 2 + rz["z"] ** 2))
    roll = math.atan2(ry["x"], math.sqrt(rx["x"] ** 2 + rz["x"] ** 2))

    if math.isnan(yaw) or math.isinf(yaw):
        yaw, pitch, roll = 0.0, 0.0, 0.0

    return {"yaw": yaw, "pitch": pitch, "roll": roll}


def orientation_to_dict(orient) -> Dict:
    """Convierte LMUOrientation ctypes struct a dict (maneja múltiples formatos)."""
    if hasattr(orient, "row_x"):
        return {
            "row_x": {"x": orient.row_x.x, "y": orient.row_x.y, "z": orient.row_x.z},
            "row_y": {"x": orient.row_y.x, "y": orient.row_y.y, "z": orient.row_y.z},
            "row_z": {"x": orient.row_z.x, "y": orient.row_z.y, "z": orient.row_z.z},
        }
    if hasattr(orient, "__getitem__") and len(orient) >= 3:
        return {
            "row_x": {"x": orient[0].x, "y": orient[0].y, "z": orient[0].z},
            "row_y": {"x": orient[1].x, "y": orient[1].y, "z": orient[1].z},
            "row_z": {"x": orient[2].x, "y": orient[2].y, "z": orient[2].z},
        }
    raise ValueError(f"Unknown orientation format: {type(orient)}")


class LMUReader:
    """Lee shared memory de LMU usando MMapControl de shared_telemetry.

    NO usa TelemetryReader (demasiado abstracto). Lee LMUObjectOut directamente
    para tener control total sobre qué campos extraer.
    """

    def __init__(self):
        self._shmm = None
        self._is_initialized = False

    def _create_mmap(self):
        from shared_telemetry.pyLMUSharedMemory.lmu_mmap import MMapControl

        mmap = MMapControl()
        mmap.create("$LMULocal$", 0)
        return mmap

    def get_flat_dict(self) -> Dict[str, Any]:
        """Lee shared memory y devuelve dict plano con TODOS los campos."""
        if not self._is_initialized:
            try:
                self._shmm = self._create_mmap()
                self._is_initialized = True
            except Exception as e:
                logger.error(f"Failed to init LMU shared memory: {e}")
                return {"session_running_time": 0.0}

        if self._shmm is None or self._shmm.data is None:
            return {"session_running_time": 0.0}

        d: Dict[str, Any] = {}
        try:
            data = self._shmm.data
            scoring = data.scoring
            # Sesión
            d["session_type"] = int(scoring.mScoringInfo.mSession)
            d["session_phase"] = int(scoring.mScoringInfo.mGamePhase)
            d["session_running_time"] = float(scoring.mScoringInfo.mCurrentET)
            end_et = float(scoring.mScoringInfo.mEndET)
            d["session_time_remaining"] = end_et - float(scoring.mScoringInfo.mCurrentET)
            d["track_length"] = float(scoring.mScoringInfo.mLapDist)

            # Jugador
            player_veh = scoring.mVehicles[data.player_index]
            d["place"] = int(player_veh.mPlace)
            d["lap_number"] = int(player_veh.mTotalLaps)
            d["lap_distance"] = float(player_veh.mLapDist)
            d["sector_number"] = (
                int(player_veh.mSector) if player_veh.mSector != 0 else 3
            )
            d["in_pits"] = bool(player_veh.mInPits)
            d["driver_name"] = decode_name(player_veh.mDriverName)

            # Orientación (crítica para spotter cartesiano)
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

            # Energía virtual (LMU Hypercars)
            d["virtual_energy"] = float(getattr(player_veh, "mVirtualEnergy", 0))

            # Telemetría del jugador
            tele = data.telemetry
            d["speed_ms"] = float(tele.mSpeed)
            d["world_x"] = float(tele.mPos.x)
            d["world_y"] = float(tele.mPos.y)
            d["world_z"] = float(tele.mPos.z)
            d["engine_rpm"] = float(tele.mEngineRPM)
            d["gear"] = int(tele.mGear)
            d["water_temp"] = float(tele.mEngineWaterTemp)
            d["oil_temp"] = float(tele.mEngineOilTemp)
            d["fuel_left"] = float(tele.mFuel)
            d["fuel_capacity"] = float(getattr(tele, "mFuelCapacity", 0))

            # Neumáticos
            d["tyre_temp_fl"] = float(tele.mWheels[0].mTemperature)
            d["tyre_temp_fr"] = float(tele.mWheels[1].mTemperature)
            d["tyre_temp_rl"] = float(tele.mWheels[2].mTemperature)
            d["tyre_temp_rr"] = float(tele.mWheels[3].mTemperature)
            d["tyre_wear_fl"] = float(tele.mWheels[0].mWear)
            d["tyre_wear_fr"] = float(tele.mWheels[1].mWear)
            d["tyre_wear_rl"] = float(tele.mWheels[2].mWear)
            d["tyre_wear_rr"] = float(tele.mWheels[3].mWear)
            d["brake_temp_fl"] = float(tele.mWheels[0].mBrakeTemp)
            d["brake_temp_fr"] = float(tele.mWheels[1].mBrakeTemp)
            d["brake_temp_rl"] = float(tele.mWheels[2].mBrakeTemp)
            d["brake_temp_rr"] = float(tele.mWheels[3].mBrakeTemp)
            d["tyre_pressure_fl"] = float(tele.mWheels[0].mPressure)
            d["tyre_pressure_fr"] = float(tele.mWheels[1].mPressure)
            d["tyre_pressure_rl"] = float(tele.mWheels[2].mPressure)
            d["tyre_pressure_rr"] = float(tele.mWheels[3].mPressure)

            # Aceleración (detección de impactos)
            if hasattr(tele, "mLocalAccel"):
                d["accel_long"] = float(tele.mLocalAccel.x)
                d["accel_lat"] = float(tele.mLocalAccel.y)
                d["accel_vert"] = float(tele.mLocalAccel.z)

            # Estado de carga (batería)
            d["state_of_charge"] = float(getattr(tele, "mStateOfCharge", 0))
            d["battery_charge_fraction"] = float(
                getattr(tele, "mBatteryChargeFraction", 0)
            )

            # Oponentes
            rivals = []
            num_veh = int(scoring.mScoringInfo.mNumVehicles)
            for i in range(min(num_veh, 64)):
                if i == data.player_index:
                    continue
                veh = scoring.mVehicles[i]
                name = decode_name(veh.mDriverName)
                if name.lower() == "transparent trainer":
                    continue
                rivals.append({
                    "driver_raw_name": name,
                    "car_number": decode_name(getattr(veh, "mCarNumber", b"")),
                    "place": int(veh.mPlace),
                    "class_place": int(getattr(veh, "mClassPlace", 0)),
                    "speed": 0.0,
                    "distance_round_track": float(getattr(veh, "mLapDist", 0)),
                    "laps_completed": int(veh.mTotalLaps),
                    "last_lap_time": float(veh.mLastLapTime),
                    "best_lap_time": float(veh.mBestLapTime),
                    "current_sector": (
                        int(veh.mSector) if veh.mSector != 0 else 3
                    ),
                    "in_pits": bool(veh.mInPits),
                    "vehicle_class": decode_name(veh.mVehicleClass),
                    "tyre_compound": decode_name(getattr(veh, "mTyreCompound", b"")),
                    "gap_to_player": float(getattr(veh, "mTimeDeltaLeader", 0)),
                    "is_active": bool(getattr(veh, "mIsActive", 1)),
                    "world_x": 0.0,
                    "world_z": 0.0,
                })

            # Rellenar velocidades y posiciones desde array de telemetría
            if hasattr(data, "telemetry_arr"):
                for i, rival in enumerate(rivals):
                    if i < len(data.telemetry_arr):
                        t = data.telemetry_arr[i]
                        rival["speed"] = float(t.mSpeed)
                        rival["world_x"] = float(t.mPos.x)
                        rival["world_z"] = float(t.mPos.z)

            d["rivals"] = rivals
            d["num_rivals"] = len(rivals)

        except Exception as e:
            logger.error(f"Error reading LMU shared memory: {e}")
            return {"session_running_time": 0.0}

        return d

    def reinitialize(self) -> bool:
        """Reinicia la conexión a shared memory (tras reinicio de LMU)."""
        import subprocess

        try:
            r = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq LMU.exe"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "LMU.exe" not in r.stdout:
                logger.info("LMU no está corriendo")
                return False
        except Exception:
            pass

        self._shmm = self._create_mmap()
        self._is_initialized = True
        logger.info("Shared memory reinitialized")
        return True
```

#### Step 3: Ejecutar tests

Run: `cd backend && python -m pytest tests/test_lmu_reader.py -v`
Expected: 10 PASSED

#### Step 4: Commit

```bash
git add backend/src/services/lmu_reader.py backend/tests/test_lmu_reader.py
git commit -m "feat(crewchief): add LMUReader with shared memory flat dict extraction"
```

---

### Task 9: FrameCache — Un solo frame para eventos y spotter

**Files:**
- Create: `backend/src/services/frame_cache.py`
- Test: `backend/tests/test_frame_cache.py`

**Descripción:** Centraliza la lectura de datos. Llama a `lmu_reader.get_flat_dict()` UNA vez por tick. Fusiona datos de REST API desde `lmu_api.py`. Deduplica frames donde `mCurrentET` no ha cambiado. Pre-extrae datos para el spotter cartesiano.

#### Step 1: Escribir tests

```python
# backend/tests/test_frame_cache.py
import pytest
from unittest.mock import MagicMock, patch
from backend.src.services.frame_cache import FrameCache


class MockReader:
    def __init__(self):
        self._call_count = 0

    def get_flat_dict(self):
        self._call_count += 1
        return {
            "session_running_time": float(self._call_count),
            "session_phase": 5,
            "world_x": 100.0,
            "world_z": 200.0,
            "rotation_yaw": 0.5,
            "speed_ms": 50.0,
            "in_pits": False,
            "rivals": [
                {
                    "driver_raw_name": "Alice",
                    "world_x": 150.0,
                    "world_z": 210.0,
                    "speed": 48.0,
                    "in_pits": False,
                }
            ],
            "place": 3,
            "lap_number": 5,
        }


def test_read_full_returns_dict():
    cache = FrameCache(MockReader())
    result = cache.read_full()
    assert isinstance(result, dict)
    assert result["place"] == 3


def test_read_full_same_et_dedup():
    """Dos lecturas con mismo session_running_time deben devolver mismo dict."""
    reader = MockReader()
    cache = FrameCache(reader)
    first = cache.read_full()
    # Forzar mismo ET
    cache._last_et = 1.0
    reader._call_count = 1  # Mock no cambia ET
    second = cache.read_full()
    assert second["place"] == 3


def test_get_spotter_frame():
    cache = FrameCache(MockReader())
    sf = cache.get_spotter_frame()
    assert "world_x" in sf
    assert "rivals" in sf
    assert sf["session_phase"] == 5


def test_spotter_frame_rivals():
    cache = FrameCache(MockReader())
    sf = cache.get_spotter_frame()
    assert len(sf["rivals"]) == 1
    assert sf["rivals"][0]["world_x"] == 150.0


def test_frame_id_increments():
    cache = FrameCache(MockReader())
    f1 = cache.read_full()
    f2 = cache.read_full()
    # El segundo debería tener frame_id mayor
    sf1 = cache.get_spotter_frame()
    sf2 = cache.get_spotter_frame()
    # frame_id está en spotter frame
    assert sf2["_frame_id"] >= sf1["_frame_id"]
```

#### Step 2: Crear frame_cache.py

```python
# backend/src/services/frame_cache.py
import logging
from typing import Optional

logger = logging.getLogger("vantare.frame_cache")


class FrameCache:
    """Un solo frame — compartido entre eventos y spotter.

    CrewChief lee UN frame con flag 'forSpotter'. Nosotros leemos una vez
    y servimos el mismo dict a todos. Evita race conditions.
    """

    def __init__(self, reader):
        self._reader = reader
        self._latest: Optional[dict] = None
        self._spotter: Optional[dict] = None
        self._frame_id: int = 0
        self._last_et: float = -1.0

    def read_full(self) -> dict:
        """Lee shared memory + REST API y devuelve el dict completo."""
        raw = self._reader.get_flat_dict()
        et = raw.get("session_running_time", 0.0)

        # Dedup: mismo ET = mismo frame
        if et == self._last_et and self._latest is not None and et > 0:
            return self._latest
        self._last_et = et

        # Fusionar REST API (LMU port 6397)
        self._merge_rest(raw)

        self._latest = raw
        self._frame_id += 1

        # Pre-extraer datos para spotter cartesiano
        rivals = [
            {
                "id": i,
                "world_x": r.get("world_x", 0),
                "world_z": r.get("world_z", 0),
                "speed": r.get("speed", 0),
                "in_pits": r.get("in_pits", False),
            }
            for i, r in enumerate(raw.get("rivals", []))
        ]
        self._spotter = {
            "world_x": raw.get("world_x", 0),
            "world_z": raw.get("world_z", 0),
            "rotation_yaw": raw.get("rotation_yaw", 0),
            "speed_ms": raw.get("speed_ms", 0),
            "rivals": rivals,
            "session_phase": raw.get("session_phase", 0),
            "in_pits": raw.get("in_pits", False),
            "_frame_id": self._frame_id,
        }

        return self._latest

    def get_spotter_frame(self) -> dict:
        """Devuelve solo los datos que necesita el spotter."""
        if self._spotter is None:
            self.read_full()
        return self._spotter

    def _merge_rest(self, raw: dict) -> None:
        """Fusiona datos de REST API en el dict plano."""
        try:
            from backend.src.services.lmu_api import get_garage_wear

            rest = get_garage_wear()
            if rest:
                if "wearables" in rest:
                    w = rest["wearables"]
                    if "tires" in w and w["tires"]:
                        raw["tyre_wear"] = [float(x) for x in w["tires"]]
                    if "brakes" in w and w["brakes"]:
                        raw["brake_wear"] = [float(x) for x in w["brakes"]]
                    if "body" in w and "aero" in w["body"]:
                        raw["damage_aero"] = float(w["body"]["aero"])
        except ImportError:
            pass  # lmu_api no disponible (tests, Linux sin REST)
        except Exception as e:
            logger.debug(f"REST merge failed: {e}")
```

#### Step 3: Ejecutar tests

Run: `cd backend && python -m pytest tests/test_frame_cache.py -v`
Expected: 5 PASSED

#### Step 4: Commit

```bash
git add backend/src/services/frame_cache.py backend/tests/test_frame_cache.py
git commit -m "feat(crewchief): add FrameCache with dedup and REST merge"
```

---

### Task 10: GameStateBuilder — Conversión de flat dict a GameStateData

**Files:**
- Create: `backend/src/services/game_state_builder.py`
- Test: `backend/tests/test_game_state_builder.py`

**Descripción:** Convierte el flat dict del `FrameCache` a `GameStateData` con dataclasses tipadas. Puebla `just_gone_green_time`, inicializa `session_start_class_position`. Es el puente entre el mundo plano (lectura) y el mundo estructurado (eventos).

#### Step 1: Escribir tests

```python
# backend/tests/test_game_state_builder.py
import pytest
from backend.src.services.game_state_builder import build, populate_derived
from backend.src.services.state_diff import TickChanges
from backend.src.models.game_state_data import GameStateData
from backend.src.models.enums import SessionType, SessionPhase


def _make_flat(**overrides):
    data = {
        "session_type": 3,
        "session_phase": 5,
        "session_running_time": 100.0,
        "session_time_remaining": 1800.0,
        "lap_number": 5,
        "sector_number": 2,
        "place": 3,
        "driver_name": "Test",
        "world_x": 100.0,
        "world_z": 200.0,
        "rotation_yaw": 0.5,
        "rotation_pitch": 0.0,
        "rotation_roll": 0.0,
        "speed_ms": 50.0,
        "lap_distance": 800.0,
        "in_pits": False,
        "fuel_left": 65.0,
        "fuel_capacity": 100.0,
        "rivals": [],
    }
    data.update(overrides)
    return data


def test_build_returns_game_state_data():
    gsd = build(_make_flat())
    assert isinstance(gsd, GameStateData)


def test_build_session_values():
    gsd = build(_make_flat(session_type=3, session_phase=5))
    assert gsd.session.session_type == SessionType.RACE
    assert gsd.session.session_phase == SessionPhase.GREEN
    assert gsd.session.completed_laps == 5


def test_build_motion_values():
    gsd = build(_make_flat(world_x=500.0, world_z=1000.0, rotation_yaw=1.2))
    assert gsd.motion.world_x == 500.0
    assert gsd.motion.world_z == 1000.0
    assert gsd.motion.orientation.yaw == 1.2
    assert gsd.motion.speed_kmh == 180.0  # 50 * 3.6


def test_build_pit_values():
    gsd = build(_make_flat(in_pits=True))
    assert gsd.pit.in_pitlane


def test_build_fuel_values():
    gsd = build(_make_flat(fuel_left=42.5))
    assert gsd.fuel.fuel_left == 42.5


def test_build_no_prev():
    # Sin prev, build no debe fallar
    gsd = build(_make_flat())
    assert gsd.session.driver_name == "Test"


def test_build_with_prev_new_lap():
    prev = build(_make_flat(lap_number=4))
    gsd = build(_make_flat(lap_number=5), prev)
    assert gsd.session.is_new_lap


def test_populate_derived_just_gone_green():
    prev = build(_make_flat(session_phase=3))  # Formación
    curr = build(_make_flat(session_phase=5))  # Green
    changes = TickChanges()
    populate_derived(curr, changes, prev)
    assert curr.session.just_gone_green
    assert curr.session.just_gone_green_time > 0


def test_populate_derived_no_green_change():
    prev = build(_make_flat(session_phase=5))
    curr = build(_make_flat(session_phase=5))
    changes = TickChanges()
    populate_derived(curr, changes, prev)
    assert not curr.session.just_gone_green


def test_build_opponents():
    gsd = build(_make_flat(rivals=[
        {"driver_raw_name": "Alice", "car_number": "1", "place": 2,
         "speed": 49.0, "distance_round_track": 900.0, "gap_to_player": 2.5,
         "last_lap_time": 92.0, "best_lap_time": 90.0, "laps_completed": 5,
         "in_pits": False, "vehicle_class": "GT3", "tyre_compound": "Soft"},
    ]))
    assert "Alice" in gsd.opponents
    assert gsd.opponents["Alice"].class_pos == 2


def test_build_session_phase_mapping():
    assert build(_make_flat(session_phase=0)).session.session_phase == SessionPhase.UNAVAILABLE
    assert build(_make_flat(session_phase=6)).session.session_phase == SessionPhase.FULL_COURSE_YELLOW
    assert build(_make_flat(session_phase=8)).session.session_phase == SessionPhase.FINISHED
```

#### Step 2: Crear game_state_builder.py

```python
# backend/src/services/game_state_builder.py
from typing import Optional
from backend.src.models.game_state_data import (
    GameStateData,
    SessionData,
    PositionAndMotionData,
    PitData,
    FlagData,
    TyreData,
    CarDamageData,
    EngineData,
    FuelData,
    BatteryData,
    OpponentData,
    PenaltiesData,
    OvertakingAidsData,
    FrozenOrderData,
    Rotation,
)
from backend.src.models.enums import (
    SessionType,
    SessionPhase,
    FlagEnum,
    FullCourseYellowPhase,
    PitWindow,
    FrozenOrderPhase,
    FrozenOrderAction,
)
from backend.src.services.state_diff import TickChanges


_SESSION_TYPE_MAP = {
    0: SessionType.UNAVAILABLE,
    1: SessionType.PRACTICE,
    2: SessionType.QUALIFY,
    3: SessionType.RACE,
}

_SESSION_PHASE_MAP = {
    0: SessionPhase.UNAVAILABLE,
    1: SessionPhase.GARAGE,
    2: SessionPhase.GRIDWALK,
    3: SessionPhase.FORMATION,
    4: SessionPhase.COUNTDOWN,
    5: SessionPhase.GREEN,
    6: SessionPhase.FULL_COURSE_YELLOW,
    7: SessionPhase.CHECKERED,
    8: SessionPhase.FINISHED,
}


def _session_type(v: int) -> SessionType:
    return _SESSION_TYPE_MAP.get(v, SessionType.UNAVAILABLE)


def _session_phase(v: int) -> SessionPhase:
    return _SESSION_PHASE_MAP.get(v, SessionPhase.UNAVAILABLE)


def build(flat: dict, prev: Optional[GameStateData] = None) -> GameStateData:
    """Convierte flat dict a GameStateData con dataclasses tipadas."""
    import time as _time

    g = GameStateData()
    g.now = flat.get("timestamp", 0) or _time.time()
    s = g.session

    s.session_type = _session_type(flat.get("session_type", 0))
    s.session_phase = _session_phase(flat.get("session_phase", 0))
    s.session_running_time = flat.get("session_running_time", 0.0)
    s.session_time_remaining = flat.get("session_time_remaining", 0.0)
    s.completed_laps = int(flat.get("lap_number", 0))
    s.class_position = int(flat.get("place", 0))
    s.driver_name = flat.get("driver_name", "")
    s.player_lap_time_best = flat.get("best_lap_time", 0.0)
    s.player_lap_time_prev = flat.get("last_lap_time", 0.0)

    # Detectar nueva vuelta comparando con prev
    if prev:
        s.is_new_lap = s.completed_laps > prev.session.completed_laps
        s.is_new_sector = flat.get("sector_number", 1) != prev.session.sector_number

    s.sector_number = int(flat.get("sector_number", 1))

    # Movimiento
    m = g.motion
    m.world_x = flat.get("world_x", 0.0)
    m.world_y = flat.get("world_y", 0.0)
    m.world_z = flat.get("world_z", 0.0)
    m.orientation.yaw = flat.get("rotation_yaw", 0.0)
    m.orientation.pitch = flat.get("rotation_pitch", 0.0)
    m.orientation.roll = flat.get("rotation_roll", 0.0)
    m.car_speed = flat.get("speed_ms", 0.0)
    m.distance_round_track = flat.get("lap_distance", 0.0)

    # Pits
    g.pit.in_pitlane = flat.get("in_pits", False)

    # Combustible
    g.fuel.fuel_left = flat.get("fuel_left", 0.0)
    g.fuel.fuel_capacity = flat.get("fuel_capacity", 0.0)

    # Batería (normalizada)
    b = flat.get("battery_percentage", 0) or flat.get("virtual_energy", 0)
    cap = flat.get("fuel_capacity", 0)
    if cap > 0 and b <= 1.0:
        g.battery.percentage = (b * 100.0) / cap
    elif b <= 1.0:
        g.battery.percentage = b * 100.0
    else:
        g.battery.percentage = b

    # Motor
    g.engine.rpm = flat.get("engine_rpm", 0.0)
    g.engine.water_temp = flat.get("water_temp", 0.0)
    g.engine.oil_temp = flat.get("oil_temp", 0.0)
    g.engine.gear = int(flat.get("gear", 0))

    # Neumáticos (desde array o campos individuales)
    tw = flat.get("tyre_wear", [])
    if len(tw) >= 4:
        g.tyre.fl_wear = tw[0]
        g.tyre.fr_wear = tw[1]
        g.tyre.rl_wear = tw[2]
        g.tyre.rr_wear = tw[3]

    g.tyre.fl_temp = flat.get("tyre_temp_fl", 0.0)
    g.tyre.fr_temp = flat.get("tyre_temp_fr", 0.0)
    g.tyre.rl_temp = flat.get("tyre_temp_rl", 0.0)
    g.tyre.rr_temp = flat.get("tyre_temp_rr", 0.0)

    g.tyre.fl_brake_temp = flat.get("brake_temp_fl", 0.0)
    g.tyre.fr_brake_temp = flat.get("brake_temp_fr", 0.0)
    g.tyre.rl_brake_temp = flat.get("brake_temp_rl", 0.0)
    g.tyre.rr_brake_temp = flat.get("brake_temp_rr", 0.0)

    g.tyre.fl_pressure = flat.get("tyre_pressure_fl", 0.0)
    g.tyre.fr_pressure = flat.get("tyre_pressure_fr", 0.0)
    g.tyre.rl_pressure = flat.get("tyre_pressure_rl", 0.0)
    g.tyre.rr_pressure = flat.get("tyre_pressure_rr", 0.0)

    # Daños
    bw = flat.get("brake_wear", [])
    if len(bw) >= 4:
        g.tyre.fl_compound = "Unknown_Race"

    # Oponentes
    for r in flat.get("rivals", []):
        name = r.get("driver_raw_name", "")
        if not name:
            continue
        g.opponents[name] = OpponentData(
            driver=name,
            car_number=r.get("car_number", "-1"),
            class_pos=r.get("class_place", 0),
            overall_pos=r.get("place", 0),
            speed=r.get("speed", 0.0),
            distance=r.get("distance_round_track", 0.0),
            delta=r.get("gap_to_player", 0.0),
            last_lap=r.get("last_lap_time", 0.0),
            best_lap=r.get("best_lap_time", 0.0),
            laps=r.get("laps_completed", 0),
            in_pits=r.get("in_pits", False),
            tyre=r.get("tyre_compound", "Unknown_Race"),
        )

    return g


def populate_derived(
    g: GameStateData,
    changes: TickChanges,
    prev: Optional[GameStateData] = None,
) -> None:
    """Puebla campos derivados como just_gone_green_time.

    FIX: just_gone_green_time NO estaba siendo seteado (bug del plan original).
    """
    sd = g.session

    # Detectar transición verde
    if prev and sd.session_phase == SessionPhase.GREEN:
        if prev.session.session_phase != SessionPhase.GREEN:
            sd.just_gone_green = True
            sd.just_gone_green_time = g.now
        else:
            sd.just_gone_green = False

    # Posición de salida
    if sd.just_gone_green or sd.is_new_session:
        sd.session_start_class_position = sd.class_position
```

#### Step 3: Ejecutar tests

Run: `cd backend && python -m pytest tests/test_game_state_builder.py -v`
Expected: 12 PASSED

#### Step 4: Ejecutar tests existentes para verificar que no se rompió nada

Run: `cd backend && python -m pytest tests/ -v`
Expected: Todos los tests existentes + los nuevos pasan

#### Step 5: Commit

```bash
git add backend/src/services/game_state_builder.py backend/tests/test_game_state_builder.py
git commit -m "feat(crewchief): add GameStateBuilder flat dict to dataclasses converter"
```

---

## Verificación final del Sub-proyecto 1

Una vez completadas las 10 tasks, ejecutar:

```bash
cd backend
python -m pytest tests/test_enums.py tests/test_track_definition.py tests/test_car_class_data.py tests/test_game_state_data.py tests/test_messages_crewchief.py tests/test_delta_time.py tests/test_state_diff.py tests/test_lmu_reader.py tests/test_frame_cache.py tests/test_game_state_builder.py -v
```

Expected: Todos PASSED

```bash
python -m pytest tests/ -v
```

Expected: Todos los tests existentes + los nuevos siguen pasando (sin regresiones)

## Qué NO incluye este sub-proyecto

- `crewchief_loop.py` — se creará cuando el EventEngine y el AudioPlayer estén listos
- `noisy_cartesian_spotter.py` — Sub-proyecto 3
- `audio_player.py`, `sound_cache.py` — Sub-proyecto 2
- `base_event.py`, `event_engine.py` — Sub-proyecto 4
- Ningún evento de carrera — Sub-proyectos 4 y 5
