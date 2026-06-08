from src.intelligence.crewchief_events.modules.penalties import PenaltiesEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_cut_track_emitted_from_penalties_module():
    module = PenaltiesEvent()
    messages = module.evaluate(
        CrewChiefFrameContext(
            previous={"track_limits_steps": 0},
            current={"track_limits_steps": 2, "num_penalties": 0, "lap_number": 3, "session_type_int": 10},
            strategy={},
            session={"phase": "race", "session_type_int": 10},
            now_monotonic=0.0,
        )
    )
    assert messages
    assert messages[0].event_id == "cut_track_warning"
