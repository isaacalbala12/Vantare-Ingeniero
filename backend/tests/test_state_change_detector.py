from shared_strategy.models import TelemetryFrame
from src.services.state_change_detector import StateChangeDetector


def _minimal_frame(**overrides) -> TelemetryFrame:
    base = dict(
        session_type="race",
        session_type_int=10,
        session_time_left=3600.0,
        session_laps_left=10.0,
        lap_number=2,
        lap_distance=100.0,
        lap_time_best=90.0,
        lap_time_previous=91.0,
        is_invalid_lap=False,
        in_garage=False,
        in_pits=False,
        pit_limiter_active=False,
        yellow_flag_active=False,
        safety_car_active=False,
        full_course_yellow_active=False,
        fuel_in_tank=50.0,
        fuel_capacity=100.0,
        fuel_used_lap_raw=0.0,
        battery_charge=100.0,
        battery_drain=0.0,
        battery_regen=0.0,
        motor_state=1,
        tyre_wear_fl=10.0,
        tyre_wear_fr=10.0,
        tyre_wear_rl=10.0,
        tyre_wear_rr=10.0,
        tyre_temp_fl=80.0,
        tyre_temp_fr=80.0,
        tyre_temp_rl=80.0,
        tyre_temp_rr=80.0,
        brake_wear_fl=0.0,
        brake_wear_fr=0.0,
        brake_wear_rl=0.0,
        brake_wear_rr=0.0,
        speed=50.0,
        throttle=0.5,
        brake=0.0,
        pos_x=0.0,
        pos_y=0.0,
        pos_z=0.0,
    )
    base.update(overrides)
    return TelemetryFrame(**base)


def test_pit_entry_detected():
    det = StateChangeDetector()
    prev = _minimal_frame(in_pits=False, lap_distance=100.0)
    curr = _minimal_frame(in_pits=True, lap_distance=100.0)
    det.detect(prev)
    events = det.detect(curr)
    assert any(e["type"] == "pit_entry" for e in events)
