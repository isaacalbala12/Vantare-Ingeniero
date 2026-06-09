from src.intelligence.crewchief_events.modules.lap_counter import LapCounterEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(prev: dict, curr: dict, session: dict | None = None) -> CrewChiefFrameContext:
    return CrewChiefFrameContext(
        previous=prev,
        current=curr,
        strategy={},
        session=session or {"phase": "race", "session_type_int": 10, "enable_lap_counter_messages": True},
        now_monotonic=1.0,
    )


def test_announces_lap_number_on_complete_detailed():
    module = LapCounterEvent()
    messages = module.evaluate(
        _ctx(
            {"lap_number": 4, "session_type_int": 10},
            {"lap_number": 5, "session_type_int": 10, "in_pits": False},
            session={"verbosity_level": "detailed", "session_type_int": 10},
        )
    )
    assert any(m.event_id == "lap_counter_announce" and "5" in m.text for m in messages)


def test_skips_non_multiple_of_five_in_normal_verbosity():
    module = LapCounterEvent()
    messages = module.evaluate(
        _ctx(
            {"lap_number": 4, "session_type_int": 10},
            {"lap_number": 5, "session_type_int": 10, "in_pits": False},
            session={"verbosity_level": "normal", "session_type_int": 10},
        )
    )
    assert any(m.event_id == "lap_counter_announce" for m in messages)


def test_normal_verbosity_skips_lap_three():
    module = LapCounterEvent()
    messages = module.evaluate(
        _ctx(
            {"lap_number": 2, "session_type_int": 10},
            {"lap_number": 3, "session_type_int": 10, "in_pits": False},
            session={"verbosity_level": "normal", "session_type_int": 10},
        )
    )
    assert not any(m.event_id == "lap_counter_announce" for m in messages)


def test_last_lap_once_when_one_lap_left():
    module = LapCounterEvent()
    m1 = module.evaluate(
        _ctx(
            {"session_laps_left": 1.5, "session_type_int": 10},
            {"session_laps_left": 1.0, "session_type_int": 10, "in_pits": False},
        )
    )
    m2 = module.evaluate(
        _ctx(
            {"session_laps_left": 1.0, "session_type_int": 10},
            {"session_laps_left": 1.0, "session_type_int": 10, "in_pits": False},
        )
    )
    assert any(m.event_id == "last_lap_race" for m in m1)
    assert not any(m.event_id == "last_lap_race" for m in m2)
