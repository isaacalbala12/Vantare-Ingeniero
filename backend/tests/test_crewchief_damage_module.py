from src.intelligence.crewchief_events.modules.damage import DamageEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(current: dict, *, now: float = 10.0, previous: dict | None = None) -> CrewChiefFrameContext:
    return CrewChiefFrameContext(
        previous=previous or {},
        current=current,
        strategy={},
        session={"phase": "race", "session_type_int": 10},
        now_monotonic=now,
    )


def test_impact_settle_reports_single_short_message():
    module = DamageEvent()
    messages = module.evaluate(
        _ctx(
            {
                "last_impact_et": 100.0,
                "last_impact_magnitude": 50.0,
                "in_pits": False,
            },
            now=0.0,
        )
    )
    assert messages == []

    messages = module.evaluate(
        _ctx(
            {
                "last_impact_et": 100.0,
                "last_impact_magnitude": 50.0,
                "in_pits": False,
            },
            now=3.5,
        )
    )
    assert len(messages) == 1
    assert messages[0].event_id == "damage_status"
    assert "moderado" in messages[0].text.lower()


def test_aero_damage_reported_as_single_message():
    module = DamageEvent()
    messages = module.evaluate(
        _ctx({"damage_aero": 30.0, "in_pits": False}, now=1.0)
    )
    assert len(messages) == 1
    assert "moderado" in messages[0].text.lower()


def test_puncture_reports_generic_not_per_wheel():
    module = DamageEvent()
    tick = {"tyre_flat_fl": True, "in_pits": False}
    assert module.evaluate(_ctx(tick, now=0.0)) == []
    module._puncture_batch_ready_at = 5.0
    messages = module.evaluate(_ctx(tick, now=6.0))
    assert len(messages) == 1
    assert "delantero izquierdo" in messages[0].text.lower()


def test_multiple_severe_damages_consolidated_with_are_you_ok():
    module = DamageEvent()
    tick = {
        "tyre_flat_fl": True,
        "tyre_flat_rr": True,
        "damage_aero": 65.0,
        "in_pits": False,
    }
    module._puncture_batch_ready_at = 5.0
    messages = module.evaluate(_ctx(tick, now=6.0))
    assert len(messages) == 1
    assert "¿Estás bien?" in messages[0].text


def test_crash_are_you_ok_after_g_spike_speed_drop_and_wait():
    module = DamageEvent()
    base = {
        "local_accel_x": 0.0,
        "local_accel_y": 0.0,
        "local_accel_z": -400.0,
        "vel_x": 0.0,
        "vel_z": 0.0,
        "in_pits": False,
    }
    assert module.evaluate(_ctx(base, now=0.0)) == []
    assert module.evaluate(_ctx(base, now=1.0)) == []
    messages = module.evaluate(_ctx(base, now=2.5))
    assert len(messages) == 1
    assert messages[0].event_id == "damage_crash_ok_0"
    assert "estás bien" in messages[0].text.lower()
