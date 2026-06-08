from src.intelligence.crewchief_events.modules.opponents import OpponentsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_opponent_pitting_from_position():
    module = OpponentsEvent()
    ctx = CrewChiefFrameContext(
        previous={
            "standing_position": 4,
            "competitors": [
                {"driver_index": 7, "driver_name": "Rival", "in_pits": False, "standing_position": 3},
            ],
            "session_type_int": 10,
        },
        current={
            "standing_position": 4,
            "competitors": [
                {"driver_index": 7, "driver_name": "Rival", "in_pits": True, "standing_position": 3},
            ],
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "enable_opponent_messages": True},
        now_monotonic=12.0,
    )
    messages = module.evaluate(ctx)
    assert messages[0].event_id == "opponent_pitting"
    assert "Rival" in messages[0].text


def test_opponent_pit_exit_adjacent():
    module = OpponentsEvent()
    ctx = CrewChiefFrameContext(
        previous={
            "standing_position": 4,
            "competitors": [{"driver_index": 7, "driver_name": "Rival", "in_pits": True, "standing_position": 3}],
            "session_type_int": 10,
        },
        current={
            "standing_position": 4,
            "competitors": [{"driver_index": 7, "driver_name": "Rival", "in_pits": False, "standing_position": 5}],
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "enable_opponent_messages": True},
        now_monotonic=5.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "opponent_pit_exit" for m in messages)
