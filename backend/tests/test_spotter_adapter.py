"""Tests para spotter_adapter."""

from src.intelligence.spotter_adapter import frame_to_spotter_tick


def test_frame_to_spotter_tick_maps_telemetry_frame():
    frame = {
        "session_type": "race",
        "in_pits": False,
        "pit_limiter_active": False,
        "safety_car_active": True,
        "full_course_yellow_active": False,
        "session_laps_left": 5.0,
        "fuel_in_tank": 30.0,
        "fuel_used_lap_raw": 3.0,
        "pos_x": 10.0,
        "pos_y": 0.0,
        "pos_z": 20.0,
        "competitors": [],
    }
    advice = {
        "competitors": [
            {"gap_to_player": -0.4},
            {"gap_to_player": 0.6},
        ],
        "fuel": {"estimated_laps_remaining": 8.5},
    }
    tick = frame_to_spotter_tick(frame, advice)
    assert tick["gap_ahead"] == 0.4
    assert tick["gap_behind"] == 0.6
    assert tick["safety_car_active"] is True
    assert tick["estimated_laps_remaining"] == 8.5


def test_legacy_tick_passthrough():
    legacy = {"gap_ahead": 1.0, "in_pits": False}
    assert frame_to_spotter_tick(legacy) is legacy
