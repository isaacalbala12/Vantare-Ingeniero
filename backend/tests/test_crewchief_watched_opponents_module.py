from src.intelligence.crewchief_events.modules.watched_opponents import WatchedOpponentsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_watched_opponent_pit_entry_only_when_watched():
    module = WatchedOpponentsEvent()
    ctx = CrewChiefFrameContext(
        previous={
            "competitors": [{"driver_index": 9, "driver_name": "Target", "in_pits": False}],
            "session_type_int": 10,
        },
        current={
            "competitors": [{"driver_index": 9, "driver_name": "Target", "in_pits": True, "standing_position": 2}],
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "watched_driver_indices": [9], "enable_watched_opponent_messages": True},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "watched_opponent_pitting" for m in messages)
