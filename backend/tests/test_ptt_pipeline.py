"""Validación pregunta PTT."""

from src.intelligence.ptt_pipeline import MIN_PILOT_QUESTION_CHARS, normalize_pilot_question


def test_normalize_accepts_valid_question():
    assert normalize_pilot_question("  como va mi ritmo?  ") == "como va mi ritmo?"


def test_normalize_rejects_empty():
    assert normalize_pilot_question("") is None
    assert normalize_pilot_question(" ") is None


def test_normalize_rejects_too_short():
    assert normalize_pilot_question("a") is None
    assert len("ab") >= MIN_PILOT_QUESTION_CHARS
    assert normalize_pilot_question("ab") == "ab"
