"""Tests para flags_monitor.py."""

from src.intelligence.flags_monitor import (
    FlagEventType,
    detect_flag_transitions,
    pick_highest_priority_event,
    snapshot_from_telemetry,
)


def test_yellow_flag_transition():
    prev = snapshot_from_telemetry({"yellow_flag_active": False})
    curr = snapshot_from_telemetry({"yellow_flag_active": True})
    events = detect_flag_transitions(prev, curr)
    assert len(events) == 1
    assert events[0].event_type == FlagEventType.YELLOW


def test_blue_flag_transition():
    prev = snapshot_from_telemetry({"blue_flag_active": False})
    curr = snapshot_from_telemetry({"blue_flag_active": True})
    events = detect_flag_transitions(prev, curr)
    assert any(e.event_type == FlagEventType.BLUE for e in events)
    assert "más rápido detrás" in events[0].message


def test_safety_car_is_critical():
    prev = snapshot_from_telemetry({"safety_car_active": False})
    curr = snapshot_from_telemetry({"safety_car_active": True})
    events = detect_flag_transitions(prev, curr)
    assert events[0].event_type == FlagEventType.SAFETY_CAR
    assert events[0].priority == 4


def test_session_stopped_red_flag():
    prev = snapshot_from_telemetry({"session_stopped": False})
    curr = snapshot_from_telemetry({"session_stopped": True})
    events = detect_flag_transitions(prev, curr)
    assert events[0].event_type == FlagEventType.RED


def test_no_events_on_first_snapshot():
    curr = snapshot_from_telemetry({"yellow_flag_active": True})
    assert detect_flag_transitions(None, curr) == []


def test_pick_highest_priority():
    prev = snapshot_from_telemetry({"blue_flag_active": False, "safety_car_active": False})
    curr = snapshot_from_telemetry({"blue_flag_active": True, "safety_car_active": True})
    events = detect_flag_transitions(prev, curr)
    best = pick_highest_priority_event(events)
    assert best is not None
    assert best.event_type == FlagEventType.SAFETY_CAR
