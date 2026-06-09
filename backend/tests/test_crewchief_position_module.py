from src.intelligence.crewchief_events.modules.position import PositionEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(previous: dict, current: dict, *, now: float = 1.0, session: dict | None = None) -> CrewChiefFrameContext:
    return CrewChiefFrameContext(
        previous=previous,
        current=current,
        strategy={},
        session=session or {"phase": "race", "session_type_int": 10},
        now_monotonic=now,
    )


def test_race_start_good_after_lap_two():
    module = PositionEvent()
    messages = module.evaluate(
        _ctx(
            {"lap_number": 1, "standing_position": 8, "start_standing_position": 8},
            {"lap_number": 2, "standing_position": 5, "start_standing_position": 8, "session_type_int": 10},
        )
    )
    assert any(m.event_id == "race_start_good" for m in messages)
    assert any("5" in m.text for m in messages)


def test_race_start_bad_after_big_loss():
    module = PositionEvent()
    messages = module.evaluate(
        _ctx(
            {"lap_number": 1, "standing_position": 3, "start_standing_position": 3},
            {"lap_number": 2, "standing_position": 9, "start_standing_position": 3, "session_type_int": 10},
        )
    )
    assert any(m.event_id == "race_start_bad" for m in messages)


def test_overtake_with_opponent_key_and_gap_samples():
    module = PositionEvent()
    competitors_before = [
        {"driver_index": 10, "standing_position": 4, "driver_name": "Leader", "in_pits": False},
        {"driver_index": 42, "standing_position": 5, "driver_name": "Rival A", "in_pits": False},
        {"driver_index": 7, "standing_position": 6, "driver_name": "Player", "in_pits": False},
    ]
    module.evaluate(
        _ctx(
            {"standing_position": 6, "time_gap_car_ahead": 0.25, "competitors": competitors_before, "session_type_int": 10},
            {"standing_position": 6, "time_gap_car_ahead": 0.25, "competitors": competitors_before, "session_type_int": 10},
            now=1.0,
        )
    )
    module._gap_samples_ahead = [0.3] * 20
    competitors_after = [
        {"driver_index": 10, "standing_position": 4, "driver_name": "Leader", "in_pits": False},
        {"driver_index": 7, "standing_position": 5, "driver_name": "Player", "in_pits": False},
        {"driver_index": 42, "standing_position": 6, "driver_name": "Rival A", "in_pits": False},
    ]
    messages = module.evaluate(
        _ctx(
            {"standing_position": 6, "time_gap_car_ahead": 0.25, "competitors": competitors_before, "session_type_int": 10},
            {"standing_position": 5, "time_gap_car_ahead": 0.22, "competitors": competitors_after, "session_type_int": 10},
            now=25.0,
        )
    )
    assert any(m.event_id == "overtake" for m in messages)


def test_position_reminder_only_in_detailed_verbosity():
    module = PositionEvent()
    messages = module.evaluate(
        _ctx(
            {"standing_position": 4, "sector": 1, "session_type_int": 10},
            {"standing_position": 4, "sector": 1, "session_type_int": 10},
            now=200.0,
            session={"phase": "race", "session_type_int": 10, "verbosity_level": "detailed"},
        )
    )
    assert any(m.event_id == "position_reminder" for m in messages)
