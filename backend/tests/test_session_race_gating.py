"""Gating solo-carrera: monitores proactivos y triggers LLM."""

from __future__ import annotations

import time

import pytest

from src.intelligence.immediate_alert import proactive_event_id, proactive_message
from src.intelligence.proactive_monitors import ProactiveMonitorSuite
from src.intelligence.triggers import (
    GapClosedTrigger,
    PitWindowOpenedTrigger,
    PushNowTrigger,
)


def test_practice_no_pit_prediction():
    suite = ProactiveMonitorSuite()
    events = suite.evaluate(
        {
            "lap_number": 5,
            "standing_position": 1,
            "competitors": [{"driver_index": 1, "standing_position": 2, "in_pits": False}],
        },
        {"pit_window_open": True},
        {"phase": "PRACTICE"},
    )
    assert not any(proactive_event_id(e) == "pit_stops" for e in events)


def test_practice3_string_no_race_start():
    suite = ProactiveMonitorSuite()
    events = suite.evaluate(
        {"lap_number": 1, "standing_position": 5, "session_type": "practice"},
        {},
        {"phase": "practice"},
    )
    assert not any(proactive_event_id(e) == "race_start" for e in events)


def test_race_emits_pit_prediction():
    from src.intelligence.crewchief_events.modules.pit_stops import PitStopsEvent
    from src.intelligence.crewchief_events.types import CrewChiefFrameContext

    module = PitStopsEvent()
    ctx = CrewChiefFrameContext(
        previous={"lap_number": 5, "in_pits": False, "session_type_int": 10},
        current={
            "lap_number": 5,
            "standing_position": 1,
            "in_pits": False,
            "session_type_int": 10,
            "competitors": [],
            "fuel_laps_remaining": 2.0,
        },
        strategy={"pit_window": {"pit_window_open": True}},
        session={"phase": "RACE", "verbosity_level": "normal", "enable_pit_stop_messages": True},
        now_monotonic=100.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "pit_stop_prediction" for m in messages)


def test_practice_still_allows_rain():
    from src.intelligence.crewchief_events.modules.rain import RainEvent
    from src.intelligence.crewchief_events.types import CrewChiefFrameContext

    module = RainEvent()
    ctx = CrewChiefFrameContext(
        previous={"raining": 0.0, "session_type": "practice"},
        current={"raining": 0.6, "session_type": "practice"},
        strategy={},
        session={"phase": "PRACTICE"},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id.startswith("rain_") for m in messages)


def test_lmu_int_practice3_via_session_state():
    suite = ProactiveMonitorSuite()
    events = suite.evaluate(
        {"lap_number": 3, "standing_position": 2, "session_type": "race"},
        {},
        {"session_type_int": 3},
    )
    assert not any(proactive_event_id(e) == "pit_stops" for e in events)


def test_gap_closed_trigger_race_only():
    trigger = GapClosedTrigger()
    trigger._battle_active = False
    tele = {"gap_ahead": 1.0, "gap_behind": 99.0, "in_pits": False, "session_type": "practice"}
    assert not trigger.applies(tele, {}, {"phase": "PRACTICE"})
    tele["session_type"] = "race"
    assert trigger.applies(tele, {}, {"phase": "RACE", "enable_gap_messages": False})


def test_pit_window_trigger_silent_in_practice():
    trigger = PitWindowOpenedTrigger()
    trigger._window_open_active = False
    strategy = {"pit_window": {"pit_window_open": True}}
    tele = {"in_pits": False, "session_type": "practice"}
    assert not trigger.applies(tele, strategy, {"phase": "PRACTICE"})


def test_push_now_trigger_silent_in_practice():
    trigger = PushNowTrigger()
    trigger._push_active = False
    strategy = {"pit_window": {"undercut_potential": True}}
    tele = {
        "in_pits": False,
        "session_type": "practice",
        "gap_behind": 1.0,
        "session_laps_left": 2.0,
    }
    assert not trigger.applies(tele, strategy, {"phase": "PRACTICE"})


def test_engine_enqueue_commentary_blocks_race_only_in_practice():
    from src.intelligence.engine import IntelligenceEngine

    engine = IntelligenceEngine(broadcast_callback=lambda _m: None)
    engine._eval_telemetry = {"session_type": "practice", "session_type_int": 1}
    engine._eval_session = {"phase": "practice", "session_type_int": 1}
    assert engine.enqueue_commentary("position_change", "Subiste a P1.", "MEDIUM") is False
    assert engine.commentary.pending_count() == 0
