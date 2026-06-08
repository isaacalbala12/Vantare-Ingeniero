"""Cutover registry: CC-owned events must not use legacy proactive paths."""

from src.intelligence.crewchief_events.cutover_registry import (
    CC_OWNED_EVENT_IDS,
    LEGACY_COMMENTARY_EVENT_IDS,
    is_cc_owned_event,
    is_legacy_commentary_allowed,
    is_ported,
)


def test_race_start_and_lap_events_are_cc_owned():
    for event_id in ("race_start", "lap_complete", "race_start_announce"):
        assert is_cc_owned_event(event_id), event_id


def test_legacy_commentary_allowlist_is_disjoint_from_cc():
    overlap = LEGACY_COMMENTARY_EVENT_IDS & CC_OWNED_EVENT_IDS
    assert not overlap


def test_penalty_prefix_owned():
    assert is_cc_owned_event("penalty_new")
    assert is_cc_owned_event("penalty_2_laps")


def test_position_event_ids_are_cc_owned():
    for event_id in (
        "position_change",
        "overtake_position_gain",
        "position_loss",
        "position_gain",
        "overtake",
        "being_overtaken",
    ):
        assert is_cc_owned_event(event_id)


def test_prefixed_modules_are_cc_owned():
    assert is_cc_owned_event("penalty_new")
    assert is_cc_owned_event("flags_fcy")
    assert is_cc_owned_event("rain_heavy")
    assert is_cc_owned_event("damage_puncture")
    assert is_cc_owned_event("fuel_about_to_run_out")
    assert is_cc_owned_event("gap_ahead_decreasing")
    assert is_cc_owned_event("opponent_pitting")
    assert is_cc_owned_event("frozen_order_instruction")
    assert is_cc_owned_event("multiclass_faster_behind")
    assert is_cc_owned_event("frozen_order")


def test_legacy_allowlist_members():
    assert is_legacy_commentary_allowed("phase_changed")
    assert is_legacy_commentary_allowed("weather_forecast")
    assert not is_legacy_commentary_allowed("race_start")


def test_is_ported_alias():
    assert is_ported("fuel")
    assert not is_ported("phase_changed")


def test_pit_stops_is_cc_owned():
    assert is_cc_owned_event("pit_stops")


def test_unrelated_events_are_not_cc_owned():
    assert not is_cc_owned_event("fuel_low")
    assert "pit_stops" in CC_OWNED_EVENT_IDS
