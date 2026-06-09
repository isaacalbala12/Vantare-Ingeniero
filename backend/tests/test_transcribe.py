"""Tests endpoint /transcribe."""

import io
import struct
import wave
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app


def _minimal_wav(duration_s: float = 0.25, sample_rate: int = 16000) -> bytes:
    n_samples = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack("<" + "h" * n_samples, *([0] * n_samples)))
    return buf.getvalue()


@pytest.fixture
def client():
    return TestClient(app)


def test_transcribe_returns_whisper_text(client):
    wav = _minimal_wav()
    with patch("src.routers.transcribe.transcribe_wav", return_value="cuantas vueltas de combustible"):
        res = client.post(
            "/transcribe",
            files={"audio": ("ptt_recording.wav", wav, "audio/wav")},
        )
    assert res.status_code == 200
    assert res.json()["text"] == "cuantas vueltas de combustible"


def test_transcribe_empty_when_asr_fails(client):
    wav = _minimal_wav()
    with patch("src.routers.transcribe.transcribe_wav", return_value=""):
        res = client.post(
            "/transcribe",
            files={"audio": ("ptt_recording.wav", wav, "audio/wav")},
        )
    assert res.status_code == 200
    assert res.json()["text"] == ""
