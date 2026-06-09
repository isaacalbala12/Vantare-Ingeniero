from src.intelligence.crewchief_events.modules.session_end import SessionEndEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(prev: dict, curr: dict) -> CrewChiefFrameContext:
    return CrewChiefFrameContext(
        previous=prev,
        current=curr,
        strategy={},
        session={"phase": "race", "enable_session_end_messages": True},
        now_monotonic=1.0,
    )


def test_victory_on_session_over():
    module = SessionEndEvent()
    messages = module.evaluate(
        _ctx(
            {"session_over": False, "lap_number": 10},
            {"session_over": True, "lap_number": 10, "standing_position": 1, "start_standing_position": 3},
        )
    )
    assert any(m.event_id == "session_victory" for m in messages)


def test_podium_finish():
    module = SessionEndEvent()
    messages = module.evaluate(
        _ctx(
            {"session_over": False, "lap_number": 8},
            {"session_over": True, "lap_number": 8, "standing_position": 2, "start_standing_position": 2},
        )
    )
    assert any(m.event_id == "session_podium" for m in messages)


def test_skips_first_lap():
    module = SessionEndEvent()
    assert not module.evaluate(
        _ctx(
            {"session_over": False, "lap_number": 0},
            {"session_over": True, "lap_number": 1, "standing_position": 5},
        )
    )
