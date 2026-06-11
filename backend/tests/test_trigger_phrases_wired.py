from src.intelligence.triggers import FuelCriticalTrigger
from src.intelligence.personality_pack import PersonalityPack


def test_fuel_critical_uses_phrase_key():
    t = FuelCriticalTrigger()
    assert t.phrase_key == "fuel_critical"
    msg = t.resolve_message(PersonalityPack("aggressive"))
    assert "boxes" in msg.lower() or "vueltas" in msg.lower()
    assert "atención:" not in msg.lower()
