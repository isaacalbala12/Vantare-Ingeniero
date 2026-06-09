from src.intelligence.crewchief_events.modules.lap_times import LapTimesEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(prev: dict, curr: dict, now: float = 100.0) -> CrewChiefFrameContext:
    return CrewChiefFrameContext(
        previous=prev,
        current=curr,
        strategy={},
        session={"phase": "race", "session_type_int": 10, "enable_lap_time_messages": True},
        now_monotonic=now,
    )


def test_personal_best_on_lap_complete():
    module = LapTimesEvent()
    messages = module.evaluate(
        _ctx(
            {"lap_number": 5, "lap_time_previous": 0, "lap_time_best": 90.0, "session_type_int": 10},
            {
                "lap_number": 6,
                "lap_time_previous": 89.95,
                "lap_time_best": 89.95,
                "lap_valid": True,
                "session_type_int": 10,
                "in_pits": False,
            },
        )
    )
    assert any(m.event_id == "lap_personal_best" for m in messages)


def test_invalid_lap_message():
    module = LapTimesEvent()
    messages = module.evaluate(
        _ctx(
            {"lap_number": 3, "session_type_int": 10},
            {
                "lap_number": 4,
                "lap_time_previous": 95.0,
                "lap_valid": False,
                "session_type_int": 10,
                "in_pits": False,
            },
        )
    )
    assert any(m.event_id == "lap_invalid" for m in messages)


def test_consistency_improving_after_five_laps():
    module = LapTimesEvent()
    module._lap_times = [92.0, 91.5, 91.0, 90.8, 90.5]
    messages = module.evaluate(
        _ctx(
            {"lap_number": 10, "lap_time_previous": 90.5, "session_type_int": 10},
            {
                "lap_number": 11,
                "lap_time_previous": 90.2,
                "lap_valid": True,
                "session_type_int": 10,
                "in_pits": False,
            },
        )
    )
    assert any(m.event_id == "lap_consistency_improving" for m in messages)


def test_sector_delta_on_sector_change():
    module = LapTimesEvent()
    module._sector_entered_at = 75.0
    module._last_sector_raw = 1
    module._best_sector_duration = {1: 30.0}
    messages = module.evaluate(
        _ctx(
            {"current_sector": 1, "lap_number": 5, "session_type_int": 10, "in_pits": False},
            {"current_sector": 2, "lap_number": 5, "session_type_int": 10, "in_pits": False},
            now=100.0,
        )
    )
    assert any(m.event_id == "sector_personal_best" for m in messages)


def test_lap_times_disabled_by_session_flag():
    module = LapTimesEvent()
    messages = module.evaluate(
        CrewChiefFrameContext(
            previous={"lap_number": 5},
            current={"lap_number": 6, "lap_time_previous": 89.9, "lap_time_best": 89.9},
            strategy={},
            session={"phase": "race", "enable_lap_time_messages": False},
            now_monotonic=1.0,
        )
    )
    assert messages == []
