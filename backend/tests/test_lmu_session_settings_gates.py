from src.intelligence.crewchief_events.modules.damage import DamageEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_damage_module_silent_when_damage_disabled():
    module = DamageEvent()
    ctx = CrewChiefFrameContext(
        previous={"damage_aero": 0.0, "session_type_int": 10},
        current={
            "damage_aero": 0.5,
            "last_impact_magnitude": 30.0,
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "session_type_int": 10, "damage_enabled": False},
        now_monotonic=1.0,
    )
    assert module.evaluate(ctx) == []


def test_fuel_module_uses_session_multiplier():
    from src.intelligence.crewchief_events.modules.fuel import FuelEvent

    module = FuelEvent()
    ctx = CrewChiefFrameContext(
        previous={"fuel_laps_remaining": 5.0, "session_type_int": 10},
        current={"fuel_laps_remaining": 4.0, "session_type_int": 10},
        strategy={},
        session={
            "phase": "race",
            "session_type_int": 10,
            "fuel_multiplier": 2.0,
            "enable_fuel_messages": True,
        },
        now_monotonic=5.0,
    )
    assert FuelEvent._fuel_laps(ctx) == 2.0
