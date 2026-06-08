from src.intelligence.crewchief_events.modules.push_now import PushNowEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(prev: dict, curr: dict, *, session: dict | None = None) -> CrewChiefFrameContext:
    return CrewChiefFrameContext(
        previous=prev,
        current=curr,
        strategy={},
        session=session or {"phase": "race", "session_type_int": 10, "enable_push_now_messages": True},
        now_monotonic=1.0,
    )


def test_push_to_win_near_end():
    module = PushNowEvent()
    messages = module.evaluate(
        _ctx(
            {"session_laps_left": 4, "in_pits": False, "session_type_int": 10},
            {
                "session_laps_left": 2,
                "in_pits": False,
                "standing_position": 2,
                "lap_time_best": 100.0,
                "gap_ahead": 5.0,
                "gap_behind": 3.0,
                "session_type_int": 10,
                "competitors": [
                    {"standing_position": 1, "lap_time_best": 101.0},
                    {"standing_position": 3, "lap_time_best": 102.0},
                ],
            },
        )
    )
    assert any(m.event_id == "push_to_win" for m in messages)


def test_push_to_hold_when_rival_faster():
    module = PushNowEvent()
    messages = module.evaluate(
        _ctx(
            {"session_laps_left": 4, "in_pits": False, "session_type_int": 10},
            {
                "session_laps_left": 2,
                "in_pits": False,
                "standing_position": 3,
                "lap_time_best": 100.0,
                "gap_behind": 1.0,
                "session_type_int": 10,
                "competitors": [{"standing_position": 4, "lap_time_best": 98.0}],
            },
        )
    )
    assert any(m.event_id == "push_to_hold" for m in messages)


def test_only_once_per_stint():
    module = PushNowEvent()
    ctx = _ctx(
        {"session_laps_left": 4, "in_pits": False, "session_type_int": 10},
        {
            "session_laps_left": 2,
            "in_pits": False,
            "standing_position": 1,
            "lap_time_best": 100.0,
            "session_type_int": 10,
        },
    )
    assert module.evaluate(ctx)
    assert not module.evaluate(ctx)
