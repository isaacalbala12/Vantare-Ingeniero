"""Whisper preload at startup."""

from unittest.mock import MagicMock, patch

import pytest

from src.services import asr_service


@pytest.fixture(autouse=True)
def reset_asr():
    asr_service.reset_asr_for_tests()
    yield
    asr_service.reset_asr_for_tests()


def test_preload_whisper_loads_model():
    mock_model = MagicMock()
    with patch("faster_whisper.WhisperModel", return_value=mock_model) as ctor:
        ok = asr_service.preload_whisper()
    assert ok is True
    assert asr_service.get_asr_status()["state"] == "ready"
    ctor.assert_called_once()


def test_preload_whisper_is_idempotent():
    mock_model = MagicMock()
    with patch("faster_whisper.WhisperModel", return_value=mock_model) as ctor:
        assert asr_service.preload_whisper() is True
        assert asr_service.preload_whisper() is True
    assert ctor.call_count == 1


def test_get_asr_status_idle_before_load():
    status = asr_service.get_asr_status()
    assert status["state"] == "idle"
    assert status["preload_mode"] in ("startup", "first_question")
