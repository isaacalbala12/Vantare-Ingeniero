from src.intelligence.crewchief_events.modules.pearls import PearlsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_pearl_on_position_gain():
    module = PearlsEvent()
    module.evaluate(
        CrewChiefFrameContext(
            previous={"standing_position": 7, "session_type_int": 10},
            current={"standing_position": 6, "session_type_int": 10},
            strategy={},
            session={"phase": "race", "session_type_int": 10, "enable_pearl_messages": True, "pearl_frequency": 1.0},
            now_monotonic=0.5,
        )
    )
    ctx = CrewChiefFrameContext(
        previous={"standing_position": 6, "session_type_int": 10},
        current={"standing_position": 5, "session_type_int": 10},
        strategy={},
            session={
                "phase": "race",
                "session_type_int": 10,
                "enable_pearl_messages": True,
                "verbosity_level": "normal",
                "pearl_frequency": 1.0,
            },
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "pearl_overtake" for m in messages)
