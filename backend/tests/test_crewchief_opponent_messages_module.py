from src.intelligence.crewchief_events.modules.opponent_messages import OpponentMessagesEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_rival_fast_lap_message():
    module = OpponentMessagesEvent()
    ctx = CrewChiefFrameContext(
        previous={
            "competitors": [{"driver_index": 2, "lap_number": 4, "lap_time_previous": 0, "lap_time_best": 98.0}],
            "session_type_int": 10,
            "lap_number": 4,
        },
        current={
            "lap_number": 5,
            "competitors": [
                {
                    "driver_index": 2,
                    "driver_name": "Rival B",
                    "lap_number": 5,
                    "lap_time_previous": 97.9,
                    "lap_time_best": 97.9,
                }
            ],
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "verbosity_level": "detailed", "enable_opponent_messages": True},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "opponent_fast_lap" for m in messages)
