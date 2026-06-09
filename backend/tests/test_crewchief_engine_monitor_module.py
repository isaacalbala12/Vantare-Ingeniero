from src.intelligence.crewchief_events.modules.engine_monitor import EngineMonitorEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_engine_water_overheat_once():
    module = EngineMonitorEvent()
    ctx = CrewChiefFrameContext(
        previous={"session_type_int": 10},
        current={"engine_water_temp": 108.0, "session_type_int": 10, "in_pits": False},
        strategy={},
        session={"phase": "race", "enable_engine_warnings": True},
        now_monotonic=1.0,
    )
    m1 = module.evaluate(ctx)
    m2 = module.evaluate(ctx)
    assert any(m.event_id == "engine_overheat" for m in m1)
    assert not m2
