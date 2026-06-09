"""F0 — campos Wave 1 en TelemetryFrame y helpers LMU."""

from shared_strategy.models import TelemetryFrame
from shared_telemetry.lmu_fields import lmu_sector_number, parse_yellow_flag_state


def test_telemetry_frame_has_raining():
    frame = TelemetryFrame(
        session_type="race",
        session_time_left=3600,
        session_laps_left=10,
        lap_number=1,
        lap_distance=0,
        lap_time_best=90,
        lap_time_previous=91,
        is_invalid_lap=False,
        in_garage=False,
        in_pits=False,
        pit_limiter_active=False,
        yellow_flag_active=False,
        safety_car_active=False,
        full_course_yellow_active=False,
        fuel_in_tank=50,
        fuel_capacity=100,
        fuel_used_lap_raw=1,
        battery_charge=80,
        battery_drain=0,
        battery_regen=0,
        tyre_wear_fl=0,
        tyre_wear_fr=0,
        tyre_wear_rl=0,
        tyre_wear_rr=0,
        tyre_temp_fl=80,
        tyre_temp_fr=80,
        tyre_temp_rl=80,
        tyre_temp_rr=80,
        brake_wear_fl=0,
        brake_wear_fr=0,
        brake_wear_rl=0,
        brake_wear_rr=0,
        speed=50,
        throttle=1,
        brake=0,
        pos_x=0,
        pos_y=0,
        pos_z=0,
    )
    assert frame.raining_intensity == 0.0
    assert frame.yellow_flag_state == 0
    assert frame.tyre_flat_fl is False
    assert frame.local_accel_z == 0.0
    assert frame.current_sector == 0


def test_parse_yellow_flag_state_from_char():
    assert parse_yellow_flag_state(b"\x04") == 4
    assert parse_yellow_flag_state(4) == 4


def test_lmu_sector_number_maps_sector3():
    assert lmu_sector_number(0) == 3
    assert lmu_sector_number(1) == 1
