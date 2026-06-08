"""Tests monitores proactivos."""

from src.intelligence.immediate_alert import ImmediateAlert, proactive_event_id, proactive_message
from src.intelligence.proactive_monitors import ProactiveMonitorSuite
from src.intelligence.verbosity_controller import VerbosityController


def test_race_start_not_emitted_from_proactive():
    """Salida la emite PositionEvent / CC @ 20 Hz, no proactive."""
    suite = ProactiveMonitorSuite()
    events = suite.evaluate(
        {"lap_number": 1, "standing_position": 5},
        {},
        {"phase": "RACE"},
    )
    assert events == []
    assert suite._last_standing == 5


def test_position_change_tracked_without_proactive_voice():
    """Cambios de posición los emite PositionEvent @ 20 Hz, no proactive."""
    suite = ProactiveMonitorSuite()
    suite.evaluate({"lap_number": 2, "standing_position": 8}, {}, {"phase": "RACE"})
    events = suite.evaluate({"lap_number": 2, "standing_position": 6}, {}, {"phase": "RACE"})
    assert suite._last_standing == 6
    assert not any("P6" in proactive_message(e) for e in events)


def test_silent_verbosity_blocks_gaps():
    vc = VerbosityController("silent")
    suite = ProactiveMonitorSuite(verbosity_should_emit=vc.should_emit_priority)
    suite._last_gap_report_at = 0
    events = suite.evaluate(
        {"lap_number": 5, "standing_position": 3, "time_gap_car_ahead": 1.2},
        {"gap_ahead": 1.2},
        {"phase": "RACE"},
    )
    assert not any(proactive_event_id(e) == "gap_update" for e in events)


def test_normal_verbosity_no_periodic_gap_updates():
    vc = VerbosityController("normal")
    suite = ProactiveMonitorSuite(verbosity_should_emit=vc.should_emit_priority)
    suite._last_gap_report_at = 0
    events = suite.evaluate(
        {"lap_number": 5, "standing_position": 3, "time_gap_car_ahead": 1.2, "time_gap_car_behind": 2.1},
        {"gap_ahead": 1.2, "gap_behind": 2.1},
        {"phase": "RACE"},
    )
    assert not any(proactive_event_id(e) == "gap_update" and "Adelante" in proactive_message(e) for e in events)
