from src.intelligence.crewchief_events.modules.overtaking_aids import OvertakingAidsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_drs_available_edge():
    module = OvertakingAidsEvent()
    ctx = CrewChiefFrameContext(
        previous={"drs_state": False, "session_type_int": 10},
        current={"drs_state": True, "session_type_int": 10},
        strategy={},
        session={"phase": "race", "enable_overtaking_aids_messages": True},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert messages[0].event_id == "drs_available"
