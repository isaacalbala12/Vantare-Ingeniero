"""Tests para SessionAdapter."""

from src.intelligence.session_adapter import (
    normalize_session_type,
    normalize_session_phase,
    SessionType,
    SessionPhase,
)


def test_normalize_session_type_int():
    assert normalize_session_type(2) == SessionType.RACE
    assert normalize_session_type(0) == SessionType.PRACTICE
    assert normalize_session_type(1) == SessionType.QUALIFY


def test_normalize_session_type_str_lowercase():
    assert normalize_session_type("qualify") == SessionType.QUALIFY
    assert normalize_session_type("race") == SessionType.RACE


def test_normalize_session_type_unknown():
    assert normalize_session_type("unknown") == SessionType.RACE
    assert normalize_session_type(99) == SessionType.RACE


def test_normalize_session_phase_finished():
    assert normalize_session_phase("checkered") == SessionPhase.FINISHED
    assert normalize_session_phase("chequered") == SessionPhase.FINISHED
    assert normalize_session_phase("finished") == SessionPhase.FINISHED


def test_normalize_session_phase_green():
    assert normalize_session_phase("green") == SessionPhase.GREEN
    assert normalize_session_phase("") == SessionPhase.GREEN


def test_normalize_session_phase_countdown():
    assert normalize_session_phase("countdown") == SessionPhase.COUNTDOWN
    assert normalize_session_phase("pre_race") == SessionPhase.COUNTDOWN
    assert normalize_session_phase("formation") == SessionPhase.COUNTDOWN
