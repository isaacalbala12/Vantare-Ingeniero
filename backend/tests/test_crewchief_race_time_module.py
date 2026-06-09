from src.intelligence.crewchief_events.modules.race_time import RaceTimeEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_time_remaining_on_lap_five_normal_verbosity():
    module = RaceTimeEvent()
    ctx = CrewChiefFrameContext(
        previous={"lap_number": 4, "session_time_left": 3600, "session_type_int": 10},
        current={"lap_number": 5, "session_time_left": 3500, "session_type_int": 10, "in_pits": False},
        strategy={},
        session={"phase": "race", "verbosity_level": "normal", "enable_race_time_messages": True},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "race_time_remaining" for m in messages)
