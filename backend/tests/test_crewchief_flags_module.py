from src.intelligence.crewchief_events.modules.flags import FlagsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_fcy_pits_closed_message_is_critical():
    module = FlagsEvent()
    ctx = CrewChiefFrameContext(
        previous={"yellow_flag_state": 0, "session_type_int": 10},
        current={
            "yellow_flag_state": 2,
            "full_course_yellow_active": True,
            "safety_car_active": True,
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "session_type_int": 10},
        now_monotonic=1.0,
    )

    messages = module.evaluate(ctx)

    assert [m.event_id for m in messages] == ["flags_fcy_pits_closed"]
    assert "cerrado" in messages[0].text.lower()
    assert messages[0].play_even_when_silenced is True
