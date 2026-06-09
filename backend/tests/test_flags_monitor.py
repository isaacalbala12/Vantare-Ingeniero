"""Tests para flags_monitor.py."""

from src.intelligence.crewchief_events.modules.flags import FlagsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext
from src.intelligence.flags_monitor import (
    FlagEventType,
    detect_flag_transitions,
    pick_highest_priority_event,
    snapshot_from_telemetry,
)


def test_yellow_flag_transition():
    prev = snapshot_from_telemetry({"local_yellow_active": False, "yellow_flag_active": False})
    curr = snapshot_from_telemetry({"local_yellow_active": True, "yellow_flag_active": True})
    events = detect_flag_transitions(prev, curr)
    assert len(events) == 1
    assert events[0].event_type == FlagEventType.YELLOW


def test_yellow_flag_from_sector_flags():
    prev = snapshot_from_telemetry({"sector_flags": [0, 0, 0], "game_phase": 5})
    curr = snapshot_from_telemetry({"sector_flags": [1, 0, 0], "game_phase": 5})
    events = detect_flag_transitions(prev, curr)
    assert any(e.event_type == FlagEventType.YELLOW for e in events)


def test_fcy_does_not_block_local_yellow_message_when_local_only():
    prev = snapshot_from_telemetry(
        {
            "local_yellow_active": False,
            "yellow_flag_active": False,
            "game_phase": 5,
        }
    )
    curr = snapshot_from_telemetry(
        {
            "local_yellow_active": True,
            "yellow_flag_active": True,
            "game_phase": 5,
            "sector_flags": [1, 0, 0],
        }
    )
    events = detect_flag_transitions(prev, curr)
    assert any(e.event_type == FlagEventType.YELLOW for e in events)


def test_blue_flag_transition():
    prev = snapshot_from_telemetry({"blue_flag_active": False})
    curr = snapshot_from_telemetry({"blue_flag_active": True})
    events = detect_flag_transitions(prev, curr)
    assert any(e.event_type == FlagEventType.BLUE for e in events)
    assert "más rápido detrás" in events[0].message


def test_safety_car_is_critical():
    prev = snapshot_from_telemetry({"safety_car_active": False, "full_course_yellow_active": False})
    curr = snapshot_from_telemetry({"safety_car_active": True, "full_course_yellow_active": False})
    events = detect_flag_transitions(prev, curr)
    assert any(e.event_type == FlagEventType.SAFETY_CAR for e in events)
    sc = next(e for e in events if e.event_type == FlagEventType.SAFETY_CAR)
    assert sc.priority == 4


def test_session_stopped_red_flag():
    prev = snapshot_from_telemetry({"session_stopped": False})
    curr = snapshot_from_telemetry({"session_stopped": True})
    events = detect_flag_transitions(prev, curr)
    assert events[0].event_type == FlagEventType.RED


def test_first_snapshot_detects_active_yellow():
    """Primer tick: tratar previous vacío para no perder bandera ya activa."""
    curr = snapshot_from_telemetry(
        {"local_yellow_active": True, "yellow_flag_active": True, "game_phase": 5}
    )
    events = detect_flag_transitions(None, curr)
    assert len(events) == 1
    assert events[0].event_type == FlagEventType.YELLOW


def test_flags_event_first_frame_with_active_local_yellow():
    module = FlagsEvent()
    ctx = CrewChiefFrameContext(
        previous=None,
        current={
            "local_yellow_active": True,
            "yellow_flag_active": True,
            "game_phase": 5,
            "sector_flags": [1, 0, 0],
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "session_type_int": 10},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "flags_yellow" for m in messages)


def test_pick_highest_priority():
    prev = snapshot_from_telemetry({"blue_flag_active": False, "safety_car_active": False})
    curr = snapshot_from_telemetry({"blue_flag_active": True, "safety_car_active": True})
    events = detect_flag_transitions(prev, curr)
    best = pick_highest_priority_event(events)
    assert best is not None
    assert best.priority == 4
