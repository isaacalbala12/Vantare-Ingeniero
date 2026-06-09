"""Tests del catálogo de plantillas Crew Chief P0/P1."""

from __future__ import annotations

import pytest

from src.intelligence.crewchief_events.templates import list_template_ids, render_template

P0_EVENTS = [
    "damage_impact",
    "damage_puncture",
    "damage_are_you_ok",
    "penalty_new",
    "penalty_countdown",
    "penalty_pit_now",
    "penalty_served",
    "fcy_pits_closed",
    "fcy_pits_open",
    "fcy_prepare_green",
    "fcy_green",
    "position_overtake",
    "position_lost",
    "rain_increasing",
    "rain_heavy",
]

P1_EVENTS = [
    "gap_ahead_decreasing",
    "push_to_win",
    "push_to_hold",
    "fuel_about_to_run_out",
    "session_victory",
    "session_finish",
    "race_start_good",
    "race_start_bad",
]


def test_all_p0_templates_exist():
    for event_id in P0_EVENTS:
        text = render_template(event_id, {})
        assert text, f"missing template for {event_id}"
        assert len(text) < 120, f"template too long for {event_id}: {text!r}"


def test_all_p1_templates_exist():
    for event_id in P1_EVENTS:
        text = render_template(event_id, {"position": 5, "gap": "1.2", "gain": 3, "lost": 4})
        assert text
        assert len(text) < 160


def test_damage_impact_severity_variants():
    assert "grave" in render_template("damage_impact", {"severity": "grave"}).lower()
    assert "moderado" in render_template("damage_impact", {"severity": "moderado"}).lower()
    assert "leve" in render_template("damage_impact", {"severity": "leve"}).lower()


def test_damage_puncture_wheel_variants():
    assert render_template("damage_puncture", {"wheel": "fl"}) == "Pinchazo delantero izquierdo."
    assert render_template("damage_puncture", {"wheel": "rr"}) == "Pinchazo trasero derecho."


def test_damage_are_you_ok_attempts():
    assert "¿Estás bien?" in render_template("damage_are_you_ok", {"attempt": 0})
    assert "Responde" in render_template("damage_are_you_ok", {"attempt": 1})
    assert "No contestas" in render_template("damage_are_you_ok", {"attempt": 2})


def test_penalty_countdown_laps():
    assert "3 vueltas" in render_template("penalty_countdown", {"laps": 3})
    assert "2 vueltas" in render_template("penalty_countdown", {"laps": 2})
    assert "1 vuelta" in render_template("penalty_countdown", {"laps": 1})


def test_legacy_penalty_alias_ids():
    assert "2 vueltas" in render_template("penalty_2_laps", {})
    assert "1 vuelta" in render_template("penalty_1_lap", {})


def test_legacy_crash_ok_aliases():
    assert render_template("damage_crash_ok_0", {}) == render_template(
        "damage_are_you_ok", {"attempt": 0}
    )


def test_position_template_interpolation():
    text = render_template(
        "position_overtake",
        {"with_position": True, "position": 3},
    )
    assert "P3" in text


def test_gap_template_interpolation():
    text = render_template("gap_ahead_decreasing", {"gap": "1.2"})
    assert "1.2" in text


def test_gap_templates_cover_all_trends():
    assert "2.1" in render_template("gap_ahead_increasing", {"gap": "2.1"})
    assert "1.4" in render_template("gap_ahead_decreasing", {"gap": "1.4"})
    assert render_template("gap_ahead_holding", {"gap": "2.0"})
    assert render_template("gap_behind_increasing", {"gap": "0.8"})
    assert render_template("gap_behind_decreasing", {"gap": "1.2"})
    assert render_template("gap_being_pressured", {})
    assert render_template("gap_holding_us_up", {})
    assert "Blanchimont" in render_template(
        "gap_ahead_decreasing",
        {"gap": "1.2", "with_corner": True, "corner": "Blanchimont"},
    )


def test_fcy_pits_closed_variants():
    assert "Safety Car" in render_template("fcy_pits_closed", {})
    assert "Bandera amarilla" in render_template(
        "fcy_pits_closed", {"safety_car": False}
    )


def test_catalog_has_expected_size():
    ids = list_template_ids()
    assert len(ids) >= len(P0_EVENTS) + len(P1_EVENTS)


@pytest.mark.parametrize("event_id", P0_EVENTS)
def test_p0_no_unresolved_placeholders(event_id: str):
    text = render_template(event_id, {})
    assert "{" not in text and "}" not in text
