from src.intelligence.crewchief_events.modules.multiclass import MulticlassEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_faster_class_warning_requires_stable_closing_context():
    module = MulticlassEvent(settle_seconds=3.0)
    frame = {
        "session_type": "race",
        "player_class": "GT3",
        "competitors": [
            {
                "driver_index": 8,
                "class_name": "Hypercar",
                "gap_to_player": -1.2,
                "relative_speed_ms": 12.0,
            }
        ],
    }
    first = CrewChiefFrameContext(None, frame, {}, {"phase": "race", "session_type_int": 10, "enable_multiclass_messages": True}, 10.0)
    second = CrewChiefFrameContext(frame, frame, {}, {"phase": "race", "session_type_int": 10, "enable_multiclass_messages": True}, 16.5)

    assert module.evaluate(first) == []
    messages = module.evaluate(second)

    assert messages[0].event_id == "multiclass_faster_behind"
    assert "clase rápida" in messages[0].text.lower()


def test_slower_class_ahead_warning():
    module = MulticlassEvent(settle_seconds=6.0)
    frame = {
        "session_type_int": 10,
        "player_class": "Hypercar",
        "competitors": [
            {"driver_index": 3, "class_name": "GT3", "gap_to_player": 0.8, "relative_speed_ms": -2.0},
        ],
    }
    first = CrewChiefFrameContext(None, frame, {}, {"phase": "race", "enable_multiclass_messages": True}, 10.0)
    second = CrewChiefFrameContext(frame, frame, {}, {"phase": "race", "enable_multiclass_messages": True}, 16.5)
    assert module.evaluate(first) == []
    assert any(m.event_id == "multiclass_slower_ahead" for m in module.evaluate(second))
