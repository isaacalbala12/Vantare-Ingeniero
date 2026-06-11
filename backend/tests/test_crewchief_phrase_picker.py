from src.intelligence.phrase_picker import trigger_phrase_for_session


def test_fuel_module_uses_human_phrase():
    from src.intelligence.crewchief_events.modules.fuel import FuelEvent

    module = FuelEvent()
    ctx = _fuel_ctx(laps=2.0)
    msg = module._eval_fuel_levels(ctx)
    assert msg is not None
    text = msg.text.lower()
    assert "atención:" not in text
    assert any(w in text for w in ("gasolina", "combustible", "vueltas", "boxes", "parada"))


def test_flags_module_uses_fcy_phrase():
    from src.intelligence.crewchief_events.modules.flags import _flag_text
    from src.intelligence.flags_monitor import FlagEvent, FlagEventType

    event = FlagEvent(
        event_type=FlagEventType.FCY,
        message="legacy",
        priority=4,
    )
    text = _flag_text(event, {"personalityProfileId": "aggressive"})
    assert text
    assert "atención:" not in text.lower()
    assert "fcy" in text.lower() or "levanta" in text.lower() or "boxes" in text.lower()


def _fuel_ctx(*, laps: float):
    from src.intelligence.crewchief_events.types import CrewChiefFrameContext

    return CrewChiefFrameContext(
        previous={"lap_number": 1},
        current={"lap_number": 2, "in_pits": False, "fuel_laps_remaining": laps},
        strategy={"fuel": {"estimated_laps_remaining": laps}},
        session={"enable_fuel_messages": True, "personalityProfileId": "standard"},
        now_monotonic=100.0,
    )
