from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from src.models.enums import (
    SessionType, SessionPhase, FlagEnum,
    FullCourseYellowPhase, PitWindow, FrozenOrderPhase,
    FrozenOrderAction,
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