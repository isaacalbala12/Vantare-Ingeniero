import time

from src.intelligence.spotter import SpotterService


def test_proximity_suppressed_during_fcy_pause_window():
    spotter = SpotterService()
    spotter.enabled = True
    spotter._fcy_spotter_paused_until = time.monotonic() + 15.0
    tick = {
        "speed_ms": 30.0,
        "vel_x": 30.0,
        "vel_z": 0.0,
        "yellow_flag_state": 1,
        "safety_car_active": True,
        "competitors": [
            {
                "driver_index": 1,
                "pos_x": 1.0,
                "pos_y": 0.0,
                "pos_z": 2.0,
                "vel_x": 30.0,
                "vel_z": 0.0,
            }
        ],
        "session_type": "RACE",
        "lap_number": 5,
        "pos_x": 0.0,
        "pos_y": 0.0,
        "pos_z": 0.0,
    }
    alerts = spotter._eval_proximity(tick)
    assert alerts == []
