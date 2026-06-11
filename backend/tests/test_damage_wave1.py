"""F2 — daño Wave 1: puncture, crash G, severidad."""

import time

from src.intelligence.damage_report import (
    classify_damage_severity,
    detect_crash_g,
    detect_puncture,
    format_puncture_message,
)


def test_damage_severity_grave_from_dent():
    tick = {"dent_severity_max": 2, "damage_aero": 50}
    assert classify_damage_severity(tick) == "grave"


def test_puncture_detected_via_mflat():
    tick = {"tyre_flat_fr": True}
    punct, idx = detect_puncture(tick)
    assert punct
    assert idx == 1


def test_crash_40g_detected():
    tick = {"local_accel_x": 0, "local_accel_y": 0, "local_accel_z": -400}
    assert detect_crash_g(tick)


def test_crash_below_threshold():
    tick = {"local_accel_x": 0, "local_accel_y": 0, "local_accel_z": -50}
    assert not detect_crash_g(tick)


def test_puncture_message():
    assert "delantero derecho" in format_puncture_message(1)


def test_multiple_severe_damage_message():
    from src.intelligence.damage_report import active_damage_items, format_damage_status_message

    tick = {"tyre_flat_fl": True, "tyre_flat_rr": True, "damage_aero": 65.0}
    items = active_damage_items(tick)
    text = format_damage_status_message(tick, items)
    assert text == "Múltiples daños en el coche. ¿Estás bien?"


def test_damage_edge_once():
    from src.intelligence.crewchief_events.modules.damage import DamageEvent

    module = DamageEvent()
    tick1 = {
        "last_impact_et": 100,
        "last_impact_magnitude": 50,
        "dent_severity_max": 1,
        "damage_aero": 30,
        "in_pits": False,
    }
    tick2 = dict(tick1)
    assert len(module.evaluate(_ctx_from_tick(tick1, now=0.0))) == 0
    first = module.evaluate(_ctx_from_tick(tick1, now=3.5))
    assert len(first) == 1
    assert first[0].event_id == "damage_status"
    second = module.evaluate(_ctx_from_tick(tick2, now=4.0))
    assert second == []


def _ctx_from_tick(tick: dict, *, now: float):
    from src.intelligence.crewchief_events.types import CrewChiefFrameContext

    return CrewChiefFrameContext(
        previous={},
        current=tick,
        strategy={},
        session={"phase": "race", "session_type_int": 10},
        now_monotonic=now,
    )


def test_puncture_reports_generic_message():
    from src.intelligence.crewchief_events.modules.damage import DamageEvent

    module = DamageEvent()
    tick = {"tyre_flat_fl": True, "in_pits": False}
    assert module.evaluate(_ctx_from_tick(tick, now=0.0)) == []
    module._puncture_batch_ready_at = 5.0
    messages = module.evaluate(_ctx_from_tick(tick, now=6.0))
    assert len(messages) == 1
    assert "delantero izquierdo" in messages[0].text.lower()
