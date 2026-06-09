from src.intelligence.crewchief_events.modules.battery import BatteryEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_battery_low_soc_message():
    module = BatteryEvent()
    ctx = CrewChiefFrameContext(
        previous={"session_type_int": 10},
        current={
            "battery_charge": 15.0,
            "battery_drain": 3.0,
            "battery_regen": 1.0,
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "enable_battery_messages": True},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert messages[0].event_id == "battery_low_soc"
