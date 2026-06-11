"""F5 — detección de adelantamientos (PositionEvent / CC @ 20 Hz)."""

from src.intelligence.crewchief_events.modules.position import PositionEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(previous: dict, current: dict, *, now: float = 1.0) -> CrewChiefFrameContext:
    return CrewChiefFrameContext(
        previous=previous,
        current=current,
        strategy={},
        session={"phase": "race", "session_type_int": 10},
        now_monotonic=now,
    )


def test_overtake_detected():
    module = PositionEvent()
    competitors_before = [
        {"driver_index": 10, "standing_position": 4, "driver_name": "Leader", "in_pits": False},
        {"driver_index": 42, "standing_position": 5, "driver_name": "Rival A", "in_pits": False},
        {"driver_index": 7, "standing_position": 6, "driver_name": "Player", "in_pits": False},
    ]
    competitors_after = [
        {"driver_index": 10, "standing_position": 3, "driver_name": "Leader", "in_pits": False},
        {"driver_index": 42, "standing_position": 5, "driver_name": "Rival A", "in_pits": False},
        {"driver_index": 7, "standing_position": 4, "driver_name": "Player", "in_pits": False},
    ]
    module.evaluate(
        _ctx(
            {"standing_position": 6, "time_gap_car_ahead": 0.25, "competitors": competitors_before, "session_type_int": 10},
            {"standing_position": 6, "time_gap_car_ahead": 0.25, "competitors": competitors_before, "session_type_int": 10},
            now=1.0,
        )
    )
    messages = module.evaluate(
        _ctx(
            {"standing_position": 6, "time_gap_car_ahead": 0.25, "competitors": competitors_before, "session_type_int": 10},
            {"standing_position": 4, "time_gap_car_ahead": 0.25, "competitors": competitors_after, "session_type_int": 10},
            now=22.0,
        )
    )
    assert any(m.event_id == "overtake_position_gain" for m in messages)


def test_no_overtake_under_yellow():
    module = PositionEvent()
    messages = module.evaluate(
        _ctx(
            {"standing_position": 6, "session_type_int": 10},
            {
                "standing_position": 4,
                "yellow_flag_active": True,
                "session_type_int": 10,
                "competitors": [],
            },
            now=22.0,
        )
    )
    assert not any(m.event_id == "overtake_position_gain" for m in messages)


def test_overtake_cooldown_20s():
    module = PositionEvent()
    module._last_opponent_ahead_key = "1"
    module._gap_samples_ahead = [0.5] * 20
    module._last_overtake_at = 100.0
    competitors_after = [
        {"driver_index": 3, "driver_name": "NewAhead", "standing_position": 3, "in_pits": False},
        {"driver_index": 1, "driver_name": "Rival", "standing_position": 5, "in_pits": False},
    ]
    messages = module.evaluate(
        _ctx(
            {"standing_position": 4, "time_gap_car_ahead": 0.25, "competitors": competitors_after, "session_type_int": 10},
            {"standing_position": 4, "time_gap_car_ahead": 0.25, "competitors": competitors_after, "session_type_int": 10},
            now=110.0,
        )
    )
    assert not any(m.event_id == "overtake" for m in messages)
