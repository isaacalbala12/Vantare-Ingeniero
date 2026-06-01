import time
from typing import Optional
from src.models.game_state_data import (
    GameStateData,
    SessionData,
    PositionAndMotionData,
    PitData,
    TyreData,
    EngineData,
    FuelData,
    BatteryData,
    OpponentData,
)
from src.models.enums import (
    SessionType,
    SessionPhase,
)
from src.services.state_diff import TickChanges


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
    g = GameStateData()
    g.now = flat.get("timestamp", 0) or time.time()
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

    if prev:
        s.is_new_lap = s.completed_laps > prev.session.completed_laps
        s.is_new_sector = flat.get("sector_number", 1) != prev.session.sector_number

    s.sector_number = int(flat.get("sector_number", 1))

    m = g.motion
    m.world_x = flat.get("world_x", 0.0)
    m.world_y = flat.get("world_y", 0.0)
    m.world_z = flat.get("world_z", 0.0)
    m.orientation.yaw = flat.get("rotation_yaw", 0.0)
    m.orientation.pitch = flat.get("rotation_pitch", 0.0)
    m.orientation.roll = flat.get("rotation_roll", 0.0)
    m.car_speed = flat.get("speed_ms", 0.0)
    m.distance_round_track = flat.get("lap_distance", 0.0)

    g.pit.in_pitlane = flat.get("in_pits", False)

    g.fuel.fuel_left = flat.get("fuel_left", 0.0)
    g.fuel.fuel_capacity = flat.get("fuel_capacity", 0.0)

    b = flat.get("battery_percentage", 0) or flat.get("virtual_energy", 0)
    cap = flat.get("fuel_capacity", 0)
    if cap > 0 and b <= 1.0:
        g.battery.percentage = (b * 100.0) / cap
    elif b <= 1.0:
        g.battery.percentage = b * 100.0
    else:
        g.battery.percentage = b

    g.engine.rpm = flat.get("engine_rpm", 0.0)
    g.engine.water_temp = flat.get("water_temp", 0.0)
    g.engine.oil_temp = flat.get("oil_temp", 0.0)
    g.engine.gear = int(flat.get("gear", 0))

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
    sd = g.session

    if prev and sd.session_phase == SessionPhase.GREEN:
        if prev.session.session_phase != SessionPhase.GREEN:
            sd.just_gone_green = True
            sd.just_gone_green_time = g.now
        else:
            sd.just_gone_green = False

    if sd.just_gone_green or sd.is_new_session:
        sd.session_start_class_position = sd.class_position