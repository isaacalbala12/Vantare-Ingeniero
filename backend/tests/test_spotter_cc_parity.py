"""Contrato paridad Crew Chief — spotter lateral (#1)."""

from __future__ import annotations

import time

from src.config import settings
from src.intelligence.spotter import SpotterService


def test_spotter_cc_default_settings():
    assert settings.SPOTTER_CLEAR_DELAY_S == 0.15
    assert settings.SPOTTER_CAR_LENGTH_M == 4.5
    assert settings.SPOTTER_CLOSING_SPEED_MS == 12.0
    assert settings.SPOTTER_HOLD_REPEAT_S == 3.0
    assert settings.SPOTTER_MIN_SPEED_MS == 5.0
    assert settings.SPOTTER_RACE_START_DELAY_S == 3.0


def test_spotter_service_wires_hold_repeat_from_settings():
    s = SpotterService(broadcast_callback=lambda m: None)
    assert s._proximity_state.hold_repeat_s == 3.0
    assert s._proximity_state.still_there_enabled is True
    assert s._proximity_state.clear_delay_s == 0.15


def test_apply_runtime_config_accepts_clear_015():
    s = SpotterService(broadcast_callback=lambda m: None)
    s.apply_runtime_config({"spotterClearDelayS": 0.15, "spotterHoldRepeatS": 3.0})
    assert s._proximity_state.clear_delay_s == 0.15
    assert s._proximity_state.hold_repeat_s == 3.0


def _side_by_side_tick(*, in_pits: bool = False, speed_ms: float = 25.0) -> dict:
    return {
        "session_type": "race",
        "session_phase": "RACE",
        "lap_number": 2,
        "in_pits": in_pits,
        "vel_x": speed_ms,
        "vel_z": 0.0,
        "vel_y": 0.0,
        "pos_x": 0.0,
        "pos_y": 0.0,
        "pos_z": 0.0,
        "ori_fwd_x": 0.0,
        "ori_fwd_z": 1.0,
        "player_class": "GT3",
        "vehicle_name": "GT3",
        "competitors": [
            {
                "driver_index": 2,
                "driver_class": "GT3",
                "driver_name": "Rival",
                "pos_x": 0.0,
                "pos_z": 3.0,
                "vel_x": speed_ms,
                "vel_z": 0.0,
                "speed": speed_ms,
                "in_pits": False,
            }
        ],
    }


def test_proximity_silent_below_min_speed():
    spotter = SpotterService(broadcast_callback=lambda m: None, proximity_threshold_m=3.0, enabled=True)
    tick = _side_by_side_tick(speed_ms=3.0)
    assert not any(a.category == "proximity" for a in spotter.evaluate(tick))


def test_proximity_silent_first_20s_after_race_start():
    spotter = SpotterService(broadcast_callback=lambda m: None, proximity_threshold_m=3.0, enabled=True)
    spotter._race_start_at = time.monotonic()
    tick = _side_by_side_tick()
    tick["lap_number"] = 1
    assert not any(a.category == "proximity" for a in spotter.evaluate(tick))


def test_proximity_silent_when_player_in_pits():
    spotter = SpotterService(broadcast_callback=lambda m: None, proximity_threshold_m=3.0, enabled=True)
    tick = _side_by_side_tick(in_pits=True)
    assert not any(a.category == "proximity" for a in spotter.evaluate(tick))


def test_pit_limiter_cc_default_timings():
    assert settings.PIT_LIMITER_GRACE_S == 3.0
    assert settings.PIT_LIMITER_EXIT_CHECK_S == 2.0
    assert settings.PIT_LIMITER_MIN_SPEED_MS == 1.0
    assert settings.PIT_LIMITER_ENTRY_WINDOW_S == 8.0
    assert settings.PIT_LIMITER_COOLDOWN_S == 30.0


def test_pit_limiter_service_wires_cc_defaults():
    s = SpotterService(broadcast_callback=lambda m: None)
    assert s.pit_limiter_grace_s == 3.0
    assert s.pit_limiter_exit_check_s == 2.0
    assert s.pit_limiter_min_speed_ms == 1.0
    assert s.pit_limiter_entry_window_s == 8.0
    assert s.pit_limiter_cooldown_s == 30.0
