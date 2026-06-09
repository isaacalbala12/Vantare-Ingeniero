"""Wave 7 gate: legacy paths must not emit CC-owned event_ids."""

import pytest

from src.intelligence.crewchief_events.cutover_registry import is_cc_owned_event
from src.intelligence.proactive_monitors import ProactiveMonitorSuite
from src.intelligence.triggers import get_all_triggers


def _collect_proactive_event_ids(telemetry: dict, strategy: dict, session: dict) -> set[str]:
    suite = ProactiveMonitorSuite()
    ids: set[str] = set()
    for evt in suite.evaluate(telemetry, strategy, session):
        if hasattr(evt, "event_id"):
            ids.add(evt.event_id)
        else:
            ids.add(evt[0])
    return ids


def test_proactive_monitors_never_emit_ported_race_start():
    session = {"phase": "RACE", "session_type_int": 10}
    tele = {"lap_number": 1, "standing_position": 5, "session_type": "RACE", "session_type_int": 10}
    ids = _collect_proactive_event_ids(tele, {}, session)
    assert "race_start" not in ids
    assert not {e for e in ids if is_cc_owned_event(e)}


def test_proactive_lap_complete_not_ported_commentary():
    suite = ProactiveMonitorSuite()
    suite._last_lap = 2
    session = {"phase": "RACE", "session_type_int": 10}
    tele = {
        "lap_number": 3,
        "lap_time_previous": 92.1,
        "session_type": "RACE",
        "session_type_int": 10,
        "session_laps_left": 10,
        "session_time_left": 1200,
    }
    ids = _collect_proactive_event_ids(tele, {}, session)
    assert "lap_complete" not in ids
    assert "gap_update" not in ids



def test_get_all_triggers_excludes_ported_llm_triggers():
    names = {t.__class__.__name__ for t in get_all_triggers()}
    assert "FuelCriticalTrigger" not in names
    assert "PushNowTrigger" not in names
    assert "PilotQuestionTrigger" in names
