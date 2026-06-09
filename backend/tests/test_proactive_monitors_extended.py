from src.intelligence.crewchief_events.modules.position import PositionEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_race_start_quality_moved_to_position_module():
    module = PositionEvent()
    ctx = CrewChiefFrameContext(
        previous={"lap_number": 1, "standing_position": 8},
        current={
            "lap_number": 2,
            "standing_position": 5,
            "start_standing_position": 8,
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "session_type_int": 10},
        now_monotonic=10.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "race_start_good" for m in messages)
    # Segunda evaluación con la misma posición no repite salida
    repeat_ctx = CrewChiefFrameContext(
        previous={"lap_number": 2, "standing_position": 5},
        current={
            "lap_number": 2,
            "standing_position": 5,
            "start_standing_position": 8,
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "session_type_int": 10},
        now_monotonic=11.0,
    )
    assert not any(m.event_id == "race_start_good" for m in module.evaluate(repeat_ctx))
