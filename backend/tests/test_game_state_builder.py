import pytest
from src.services.game_state_builder import build, populate_derived
from src.services.state_diff import TickChanges
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase


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
    assert gsd.motion.speed_kmh == 180.0


def test_build_pit_values():
    gsd = build(_make_flat(in_pits=True))
    assert gsd.pit.in_pitlane


def test_build_fuel_values():
    gsd = build(_make_flat(fuel_left=42.5))
    assert gsd.fuel.fuel_left == 42.5


def test_build_no_prev():
    gsd = build(_make_flat())
    assert gsd.session.driver_name == "Test"


def test_build_with_prev_new_lap():
    prev = build(_make_flat(lap_number=4))
    gsd = build(_make_flat(lap_number=5), prev)
    assert gsd.session.is_new_lap


def test_populate_derived_just_gone_green():
    prev = build(_make_flat(session_phase=3))
    curr = build(_make_flat(session_phase=5))
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