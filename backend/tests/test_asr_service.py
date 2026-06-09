"""ASR service unit tests (Whisper mocked)."""

from unittest.mock import MagicMock, patch

from src.services.asr_service import reset_asr_for_tests, transcribe_wav


def setup_function():
    reset_asr_for_tests()


def teardown_function():
    reset_asr_for_tests()


def test_transcribe_wav_rejects_tiny_payload():
    assert transcribe_wav(b"") == ""
    assert transcribe_wav(b"x" * 50) == ""


def test_transcribe_wav_returns_joined_segments():
    seg1 = MagicMock(text=" cuantas vueltas")
    seg2 = MagicMock(text=" de combustible")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([seg1, seg2], MagicMock())

    with patch("src.services.asr_service._get_model", return_value=mock_model):
        out = transcribe_wav(b"0" * 2000)

    assert out == "cuantas vueltas de combustible"
    mock_model.transcribe.assert_called_once()
