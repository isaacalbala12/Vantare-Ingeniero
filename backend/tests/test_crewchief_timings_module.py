from src.intelligence.crewchief_events.modules.timings import TimingsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(prev: dict, curr: dict, session: dict | None = None, now: float = 30.0) -> CrewChiefFrameContext:
    return CrewChiefFrameContext(
        previous=prev,
        current=curr,
        strategy={},
        session=session or {"phase": "race", "session_type_int": 10, "enable_gap_messages": True},
        now_monotonic=now,
    )


def test_gap_messages_off_when_disabled():
    module = TimingsEvent()
    messages = module.evaluate(
        _ctx(
            {"time_gap_car_ahead": 2.0, "sector": 1, "session_type_int": 10},
            {"time_gap_car_ahead": 1.2, "sector": 2, "session_type_int": 10},
            session={"phase": "race", "session_type_int": 10, "enable_gap_messages": False},
        )
    )
    assert messages == []


def test_gap_in_front_decreasing_uses_sector_gate():
    module = TimingsEvent()
    module._sectors_until_next_ahead = 0
    module.evaluate(_ctx({"time_gap_car_ahead": 2.0, "sector": 1, "session_type_int": 10}, {"time_gap_car_ahead": 1.8, "sector": 1, "session_type_int": 10}))
    module.evaluate(_ctx({"time_gap_car_ahead": 1.8, "sector": 1, "session_type_int": 10}, {"time_gap_car_ahead": 1.5, "sector": 1, "session_type_int": 10}))
    messages = module.evaluate(
        _ctx(
            {"time_gap_car_ahead": 1.5, "sector": 1, "session_type_int": 10},
            {"time_gap_car_ahead": 1.2, "sector": 2, "session_type_int": 10},
        )
    )
    assert messages[0].event_id == "gap_ahead_decreasing"
    assert "1.2" in messages[0].text
    assert messages[0].validation_key == "gap:ahead:decreasing"


def test_gap_in_front_increasing_on_sector_change():
    module = TimingsEvent()
    module._sectors_until_next_ahead = 0
    for gap in (2.0, 2.3, 2.6):
        module.evaluate(
            _ctx(
                {"time_gap_car_ahead": gap - 0.1, "sector": 1, "session_type_int": 10},
                {"time_gap_car_ahead": gap, "sector": 1, "session_type_int": 10},
            )
        )
    messages = module.evaluate(
        _ctx(
            {"time_gap_car_ahead": 2.6, "sector": 1, "session_type_int": 10},
            {"time_gap_car_ahead": 2.9, "sector": 2, "session_type_int": 10},
        )
    )
    assert any(m.event_id == "gap_ahead_increasing" for m in messages)


def test_no_gap_message_same_sector():
    module = TimingsEvent()
    module._sectors_until_next_ahead = 0
    ctx = _ctx(
        {"time_gap_car_ahead": 2.0, "sector": 2, "session_type_int": 10},
        {"time_gap_car_ahead": 1.5, "sector": 2, "session_type_int": 10},
    )
    assert module.evaluate(ctx) == []


def test_gap_being_pressured_after_sustained_close_gap():
    module = TimingsEvent()
    prev = {"time_gap_car_behind": 0.8, "sector": 1, "session_type_int": 10, "in_pits": False}
    curr = {"time_gap_car_behind": 0.8, "sector": 1, "session_type_int": 10, "in_pits": False}
    module.evaluate(_ctx(prev, curr, now=0.0))
    messages = module.evaluate(_ctx(prev, curr, now=12.0))
    assert any(m.event_id == "gap_being_pressured" for m in messages)


def test_sector_gap_sequence_fixture():
    from tests.fixtures.timings.helpers import load_fixture, replay_timings_fixture

    messages = replay_timings_fixture("sector_gap_sequence.json")
    expect = load_fixture("sector_gap_sequence.json")["expect"]
    ids = [m.event_id for m in messages]
    assert len(messages) >= expect["min_messages"]
    assert expect["event_ids"][0] in ids
