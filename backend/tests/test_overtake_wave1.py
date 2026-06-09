"""F5 — detección de adelantamientos."""

import time

from src.intelligence.immediate_alert import ImmediateAlert
from src.intelligence.proactive_monitors import ProactiveMonitorSuite


def _overtake_telemetry(**overrides):
    base = {
        "standing_position": 4,
        "competitors": [
            {"driver_index": 1, "driver_name": "Rival", "standing_position": 5, "in_pits": False},
            {"driver_index": 2, "driver_name": "Behind", "standing_position": 6, "in_pits": False},
        ],
        "time_gap_car_ahead": 2.0,
        "time_gap_car_behind": 0.5,
        "in_pits": False,
        "session_type": "RACE",
        "yellow_flag_active": False,
        "full_course_yellow_active": False,
    }
    base.update(overrides)
    return base


def test_overtake_detected():
    monitor = ProactiveMonitorSuite()
    monitor._last_opponent_ahead_key = "1"
    monitor._gap_samples_ahead = [0.5] * 20
    telemetry = _overtake_telemetry(
        standing_position=4,
        competitors=[
            {"driver_index": 3, "driver_name": "NewAhead", "standing_position": 3, "in_pits": False},
            {"driver_index": 1, "driver_name": "Rival", "standing_position": 5, "in_pits": False},
        ],
    )
    events = monitor._detect_overtakes(telemetry, time.monotonic(), {"phase": "RACE"})
    overtakes = [e for e in events if isinstance(e, ImmediateAlert) and e.event_id == "overtake"]
    assert len(overtakes) >= 1


def test_no_overtake_under_yellow():
    monitor = ProactiveMonitorSuite()
    telemetry = _overtake_telemetry(yellow_flag_active=True)
    assert monitor._detect_overtakes(telemetry, time.monotonic(), {"phase": "RACE"}) == []


def test_overtake_cooldown_20s():
    monitor = ProactiveMonitorSuite()
    monitor._last_overtake_at = time.monotonic()
    monitor._last_opponent_ahead_key = "1"
    monitor._gap_samples_ahead = [0.5] * 20
    telemetry = _overtake_telemetry(
        competitors=[
            {"driver_index": 3, "driver_name": "NewAhead", "standing_position": 3, "in_pits": False},
            {"driver_index": 1, "driver_name": "Rival", "standing_position": 5, "in_pits": False},
        ],
    )
    assert monitor._detect_overtakes(telemetry, time.monotonic(), {"phase": "RACE"}) == []
