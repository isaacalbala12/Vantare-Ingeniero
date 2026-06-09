"""Tests de validación de pilot_question en websocket."""

from src.routers.websocket import _normalize_pilot_question


def test_normalize_pilot_question_truncates_long_input():
    long_q = "a" * 600
    result = _normalize_pilot_question(long_q)
    assert result is not None
    assert len(result) <= 512


def test_normalize_pilot_question_rejects_empty():
    assert _normalize_pilot_question("") is None
    assert _normalize_pilot_question("   ") is None
