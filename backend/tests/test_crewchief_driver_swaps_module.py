from src.intelligence.crewchief_events.modules.driver_swaps import DriverSwapsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_driver_name_change_emits_swap_message():
    module = DriverSwapsEvent()
    module.evaluate(
        CrewChiefFrameContext(
            previous={"driver_name": "Alice", "session_type_int": 10},
            current={"driver_name": "Alice", "session_type_int": 10},
            strategy={},
            session={"phase": "race", "session_type_int": 10, "enable_driver_swap_messages": True},
            now_monotonic=1.0,
        )
    )
    ctx = CrewChiefFrameContext(
        previous={"driver_name": "Alice", "session_type_int": 10},
        current={"driver_name": "Bob", "session_type_int": 10},
        strategy={},
        session={"phase": "race", "session_type_int": 10, "enable_driver_swap_messages": True},
        now_monotonic=2.0,
    )
    messages = module.evaluate(ctx)
    assert len(messages) == 1
    assert messages[0].event_id == "driver_swap_detected"
    assert "Bob" in messages[0].text


def test_stint_fifteen_minutes_remaining():
    module = DriverSwapsEvent()
    ctx = CrewChiefFrameContext(
        previous={"driver_stint_seconds_remaining": 901, "session_type_int": 10},
        current={"driver_stint_seconds_remaining": 899, "session_type_int": 10},
        strategy={},
        session={"phase": "race", "session_type_int": 10, "enable_driver_swap_messages": True},
        now_monotonic=10.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "driver_swap_15_min" for m in messages)
