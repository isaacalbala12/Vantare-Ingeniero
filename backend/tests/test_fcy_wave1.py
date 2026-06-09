"""F3 — fases FCY Wave 1."""

from src.intelligence.flags_monitor import (
    FlagEventType,
    FlagSnapshot,
    detect_flag_transitions,
    detect_fcy_phase_transitions,
)


def test_fcy_phase_transition_pending():
    prev = FlagSnapshot(fcy_phase=0)
    curr = FlagSnapshot(fcy_phase=1, safety_car=True, fcy=True)
    events = detect_fcy_phase_transitions(prev, curr)
    assert any(e.event_type == FlagEventType.FCY for e in events)


def test_fcy_phase_transition_pits_closed():
    prev = FlagSnapshot(fcy_phase=0)
    curr = FlagSnapshot(fcy_phase=2, safety_car=True, fcy=True)
    events = detect_fcy_phase_transitions(prev, curr)
    assert any(e.event_type == FlagEventType.FCY_PITS_CLOSED for e in events)


def test_fcy_phase_transition_pits_open():
    prev = FlagSnapshot(fcy_phase=2, safety_car=True, fcy=True)
    curr = FlagSnapshot(fcy_phase=4, safety_car=True, fcy=True)
    events = detect_fcy_phase_transitions(prev, curr)
    assert any(e.event_type == FlagEventType.FCY_PITS_OPEN for e in events)


def test_fcy_phase_transition_green_fallback():
    prev = FlagSnapshot(fcy_phase=0, game_phase=6, safety_car=True, fcy=True)
    curr = FlagSnapshot(fcy_phase=0, game_phase=5, safety_car=False, fcy=False, yellow=False)
    events = detect_flag_transitions(prev, curr)
    assert any(e.event_type == FlagEventType.GREEN for e in events)
