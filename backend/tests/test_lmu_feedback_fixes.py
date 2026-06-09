"""Tests daño LMU + mensajes ingeniero (feedback sesión LMU)."""

from shared_telemetry.lmu_damage import damage_fields_from_player_telemetry
from src.intelligence.damage_report import (
    IMPACT_MAGNITUDE_MIN,
    classify_damage_severity,
    format_impact_damage_message,
)
from src.intelligence.immediate_alert import proactive_event_id, proactive_message
from src.intelligence.proactive_monitors import ProactiveMonitorSuite
from src.intelligence.spotter import SpotterService


class _FakeTele:
    def __init__(self, dents, detached=False, impact_et=0.0, impact_mag=0.0):
        self.mDentSeverity = dents
        self.mDetached = detached
        self.mLastImpactET = impact_et
        self.mLastImpactMagnitude = impact_mag


def test_damage_fields_from_lmu_telemetry():
    tele = _FakeTele([2, 1, 0, 0, 0, 0, 0, 0], impact_et=12.5, impact_mag=800.0)
    fields = damage_fields_from_player_telemetry(tele)
    assert fields["dent_severity_max"] == 2
    assert fields["damage_aero"] > 0
    assert fields["last_impact_et"] == 12.5
    assert fields["last_impact_magnitude"] == 800.0


def test_classify_grave_damage():
    tick = {"dent_severity_max": 2, "dent_severity_avg": 1.5, "damage_aero": 75, "detached": False}
    assert classify_damage_severity(tick) == "grave"


def test_impact_message_moderate():
    tick = {
        "dent_severity_max": 1,
        "dent_severity_avg": 0.5,
        "damage_aero": 30,
        "detached": False,
        "last_impact_magnitude": 500,
    }
    msg = format_impact_damage_message(tick)
    assert "moderado" in msg.lower() or "impacto" in msg.lower()


def test_no_position_change_in_qualifying():
    suite = ProactiveMonitorSuite()
    suite.evaluate({"lap_number": 1, "standing_position": 5}, {}, {"phase": "QUALIFYING"})
    events = suite.evaluate({"lap_number": 1, "standing_position": 8}, {}, {"phase": "QUALIFYING"})
    assert not any(proactive_event_id(e) == "position_change" for e in events)


def test_no_pit_prediction_in_practice():
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


def test_no_periodic_gap_updates():
    suite = ProactiveMonitorSuite()
    suite._last_gap_report_at = 0
    events = suite.evaluate(
        {"lap_number": 5, "standing_position": 3, "time_gap_car_ahead": 1.2, "time_gap_car_behind": 2.0},
        {"gap_ahead": 1.2, "gap_behind": 2.0},
        {"phase": "RACE"},
    )
    assert not any(
        proactive_event_id(e) == "gap_update" and "Adelante" in proactive_message(e) for e in events
    )


def test_impact_damage_via_spotter():
    spotter = SpotterService(broadcast_callback=lambda m: None)
    tick = {
        "last_impact_et": 10.0,
        "last_impact_magnitude": IMPACT_MAGNITUDE_MIN + 100,
        "dent_severity_max": 2,
        "dent_severity_avg": 1.0,
        "damage_aero": 50,
        "detached": False,
    }
    alerts = spotter.evaluate(tick)
    assert any(a.category == "damage" and "golpe" in a.message.lower() for a in alerts)


def test_personal_fast_lap_moved_to_cc_lap_times():
    """Post Task 48: vuelta rápida personal la emite LapTimesEvent, no proactive."""
    from src.intelligence.crewchief_events.modules.lap_times import LapTimesEvent
    from src.intelligence.crewchief_events.types import CrewChiefFrameContext

    module = LapTimesEvent()
    ctx = CrewChiefFrameContext(
        previous={"lap_number": 2, "lap_time_best": 90.0, "session_type_int": 10},
        current={
            "lap_number": 3,
            "lap_time_previous": 89.5,
            "lap_time_best": 89.5,
            "lap_valid": True,
            "session_type_int": 10,
            "in_pits": False,
        },
        strategy={},
        session={"phase": "PRACTICE", "enable_lap_time_messages": True},
        now_monotonic=100.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "lap_personal_best" for m in messages)


def test_competitor_fast_lap_not_from_proactive():
    suite = ProactiveMonitorSuite()
    events = suite.evaluate(
        {
            "lap_number": 3,
            "competitors": [
                {
                    "driver_index": 7,
                    "driver_name": "Rival Test",
                    "lap_number": 3,
                    "lap_time_previous": 88.0,
                    "lap_time_best": 88.0,
                }
            ],
        },
        {},
        {"phase": "RACE"},
    )
    assert not any(proactive_event_id(e) == "fast_lap" for e in events)
