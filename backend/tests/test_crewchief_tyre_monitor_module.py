from src.intelligence.crewchief_events.modules.tyre_monitor import TyreMonitorEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(curr: dict, strategy: dict | None = None, now: float = 10.0):
    return CrewChiefFrameContext(
        previous={"session_type_int": 10, "in_pits": False},
        current={**curr, "session_type_int": 10, "in_pits": False},
        strategy=strategy or {},
        session={"phase": "race", "enable_tyre_temp_messages": True, "enable_tyre_wear_messages": True},
        now_monotonic=now,
    )


def test_hot_tyre_message_once():
    module = TyreMonitorEvent()
    m1 = module.evaluate(_ctx({"tyre_temp_fl": 110.0}))
    m2 = module.evaluate(_ctx({"tyre_temp_fl": 110.0}, now=20.0))
    assert any(x.event_id == "tyre_hot" for x in m1)
    assert not any(x.event_id == "tyre_hot" for x in m2)


def test_wear_high_from_strategy():
    module = TyreMonitorEvent()
    messages = module.evaluate(_ctx({}, strategy={"tyre_wear": {"fl": 78, "fr": 76, "rl": 74, "rr": 72}}))
    assert any(m.event_id == "tyre_wear_high" for m in messages)


def test_brake_wear_high():
    module = TyreMonitorEvent()
    messages = module.evaluate(_ctx({}, strategy={"brake_wear": {"fl": 60, "fr": 85, "rl": 50, "rr": 55}}))
    assert any(m.event_id == "brake_wear_high" for m in messages)
