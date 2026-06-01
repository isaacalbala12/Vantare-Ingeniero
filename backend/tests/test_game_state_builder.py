"""Tests del GameStateBuilder — conversión flat dict a GameStateData.

Cobertura:
- build(): cada campo se mapea correctamente
- _session_type / _session_phase: enums correctos
- Datos derivados: opponents, tyre_wear, batería
- populate_derived: just_gone_green, session_start_class_position
- Casos borde: campos vacíos, defaults
"""
import pytest
from src.services.game_state_builder import build, populate_derived
from src.services.state_diff import TickChanges
from src.models.game_state_data import GameStateData
from src.models.enums import (
    SessionType, SessionPhase,
)


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


class TestBuild:
    def test_returns_game_state_data(self):
        gsd = build(_make_flat())
        assert isinstance(gsd, GameStateData)

    def test_session_type_race(self):
        gsd = build(_make_flat(session_type=3))
        assert gsd.session.session_type == SessionType.RACE

    def test_session_type_practice(self):
        gsd = build(_make_flat(session_type=1))
        assert gsd.session.session_type == SessionType.PRACTICE

    def test_session_type_qualify(self):
        gsd = build(_make_flat(session_type=2))
        assert gsd.session.session_type == SessionType.QUALIFY

    def test_session_type_unknown_maps_to_unavailable(self):
        gsd = build(_make_flat(session_type=99))
        assert gsd.session.session_type == SessionType.UNAVAILABLE

    def test_session_phase_green(self):
        gsd = build(_make_flat(session_phase=5))
        assert gsd.session.session_phase == SessionPhase.GREEN

    def test_session_phase_fcy(self):
        gsd = build(_make_flat(session_phase=6))
        assert gsd.session.session_phase == SessionPhase.FULL_COURSE_YELLOW

    def test_session_phase_checkered(self):
        gsd = build(_make_flat(session_phase=7))
        assert gsd.session.session_phase == SessionPhase.CHECKERED

    def test_session_phase_finished(self):
        gsd = build(_make_flat(session_phase=8))
        assert gsd.session.session_phase == SessionPhase.FINISHED

    def test_session_phase_unknown_maps_to_unavailable(self):
        gsd = build(_make_flat(session_phase=99))
        assert gsd.session.session_phase == SessionPhase.UNAVAILABLE

    def test_motion_world_coordinates(self):
        gsd = build(_make_flat(world_x=500.0, world_z=1000.0))
        assert gsd.motion.world_x == 500.0
        assert gsd.motion.world_z == 1000.0

    def test_motion_orientation(self):
        gsd = build(_make_flat(rotation_yaw=1.2, rotation_pitch=0.3))
        assert gsd.motion.orientation.yaw == 1.2
        assert gsd.motion.orientation.pitch == 0.3

    def test_motion_speed_kmh(self):
        gsd = build(_make_flat(speed_ms=50.0))
        assert gsd.motion.speed_kmh == 180.0  # 50 m/s * 3.6

    def test_motion_distance(self):
        gsd = build(_make_flat(lap_distance=1500.0))
        assert gsd.motion.distance_round_track == 1500.0

    def test_pit_in_pitlane(self):
        gsd = build(_make_flat(in_pits=True))
        assert gsd.pit.in_pitlane is True

    def test_pit_not_in_pitlane(self):
        gsd = build(_make_flat(in_pits=False))
        assert gsd.pit.in_pitlane is False

    def test_fuel_values(self):
        gsd = build(_make_flat(fuel_left=42.5, fuel_capacity=100.0))
        assert gsd.fuel.fuel_left == 42.5
        assert gsd.fuel.fuel_capacity == 100.0

    def test_driver_name(self):
        gsd = build(_make_flat(driver_name="Isaac"))
        assert gsd.session.driver_name == "Isaac"

    def test_class_position(self):
        gsd = build(_make_flat(place=7))
        assert gsd.session.class_position == 7

    def test_completed_laps(self):
        gsd = build(_make_flat(lap_number=12))
        assert gsd.session.completed_laps == 12

    def test_sector_number(self):
        gsd = build(_make_flat(sector_number=3))
        assert gsd.session.sector_number == 3

    def test_engine_rpm(self):
        gsd = build(_make_flat(engine_rpm=7500.0))
        assert gsd.engine.rpm == 7500.0

    def test_engine_gear(self):
        gsd = build(_make_flat(gear=4))
        assert gsd.engine.gear == 4

    def test_engine_temps(self):
        gsd = build(_make_flat(water_temp=92.0, oil_temp=110.0))
        assert gsd.engine.water_temp == 92.0
        assert gsd.engine.oil_temp == 110.0

    def test_tyre_temperatures(self):
        gsd = build(_make_flat(
            tyre_temp_fl=80.0, tyre_temp_fr=82.0,
            tyre_temp_rl=85.0, tyre_temp_rr=87.0,
        ))
        assert gsd.tyre.fl_temp == 80.0
        assert gsd.tyre.fr_temp == 82.0
        assert gsd.tyre.rl_temp == 85.0
        assert gsd.tyre.rr_temp == 87.0

    def test_tyre_wear_from_rest(self):
        """Si tyre_wear viene como lista (REST API), se mapea a fl/fr/rl/rr."""
        gsd = build(_make_flat(tyre_wear=[0.1, 0.2, 0.3, 0.4]))
        assert gsd.tyre.fl_wear == 0.1
        assert gsd.tyre.fr_wear == 0.2
        assert gsd.tyre.rl_wear == 0.3
        assert gsd.tyre.rr_wear == 0.4

    def test_tyre_wear_ignores_short_list(self):
        gsd = build(_make_flat(tyre_wear=[0.1, 0.2]))  # Solo 2
        # No debe setear nada (default 0)
        assert gsd.tyre.fl_wear == 0.0

    def test_brake_temperatures(self):
        gsd = build(_make_flat(
            brake_temp_fl=400.0, brake_temp_fr=410.0,
            brake_temp_rl=420.0, brake_temp_rr=430.0,
        ))
        assert gsd.tyre.fl_brake_temp == 400.0
        assert gsd.tyre.rr_brake_temp == 430.0

    def test_tyre_pressures(self):
        gsd = build(_make_flat(
            tyre_pressure_fl=27.0, tyre_pressure_rr=28.0,
        ))
        assert gsd.tyre.fl_pressure == 27.0
        assert gsd.tyre.rr_pressure == 28.0

    def test_opponents_extracted(self):
        gsd = build(_make_flat(rivals=[
            {"driver_raw_name": "Alice", "car_number": "1", "place": 2,
             "speed": 49.0, "distance_round_track": 900.0, "gap_to_player": 2.5,
             "last_lap_time": 92.0, "best_lap_time": 90.0, "laps_completed": 5,
             "in_pits": False, "vehicle_class": "GT3", "tyre_compound": "Soft"},
            {"driver_raw_name": "Bob", "car_number": "2", "place": 3,
             "speed": 48.0, "distance_round_track": 850.0, "gap_to_player": 3.5,
             "last_lap_time": 93.0, "best_lap_time": 91.0, "laps_completed": 5,
             "in_pits": False, "vehicle_class": "GT3", "tyre_compound": "Medium"},
        ]))
        assert "Alice" in gsd.opponents
        assert "Bob" in gsd.opponents
        assert gsd.opponents["Alice"].class_pos == 2
        assert gsd.opponents["Bob"].class_pos == 3
        assert gsd.opponents["Alice"].tyre == "Soft"

    def test_opponent_without_name_ignored(self):
        """Oponentes sin nombre no se añaden."""
        gsd = build(_make_flat(rivals=[
            {"driver_raw_name": "", "place": 1},
        ]))
        assert len(gsd.opponents) == 0


class TestBuildWithPrev:
    def test_new_lap_detected_with_prev(self):
        prev = build(_make_flat(lap_number=4))
        gsd = build(_make_flat(lap_number=5), prev)
        assert gsd.session.is_new_lap is True

    def test_same_lap_not_new(self):
        prev = build(_make_flat(lap_number=5))
        gsd = build(_make_flat(lap_number=5), prev)
        assert gsd.session.is_new_lap is False

    def test_new_sector_with_prev(self):
        prev = build(_make_flat(sector_number=1))
        gsd = build(_make_flat(sector_number=2), prev)
        assert gsd.session.is_new_sector is True


class TestPopulateDerived:
    def test_just_gone_green_set(self):
        prev = build(_make_flat(session_phase=3))
        curr = build(_make_flat(session_phase=5))
        changes = TickChanges()
        populate_derived(curr, changes, prev)
        assert curr.session.just_gone_green is True
        assert curr.session.just_gone_green_time > 0

    def test_still_green_not_set(self):
        prev = build(_make_flat(session_phase=5))
        curr = build(_make_flat(session_phase=5))
        changes = TickChanges()
        populate_derived(curr, changes, prev)
        assert curr.session.just_gone_green is False

    def test_fcy_to_green(self):
        prev = build(_make_flat(session_phase=6))
        curr = build(_make_flat(session_phase=5))
        changes = TickChanges()
        populate_derived(curr, changes, prev)
        assert curr.session.just_gone_green is True

    def test_session_start_position_set(self):
        curr = build(_make_flat(place=5))
        curr.session.just_gone_green = True
        changes = TickChanges()
        populate_derived(curr, changes, None)
        assert curr.session.session_start_class_position == 5

    def test_session_start_position_on_new_session(self):
        curr = build(_make_flat(place=3))
        curr.session.is_new_session = True
        changes = TickChanges()
        populate_derived(curr, changes, None)
        assert curr.session.session_start_class_position == 3
