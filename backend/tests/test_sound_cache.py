import os
import tempfile
import wave
import struct
import pytest
from src.services.sound_cache import SoundCache, SoundEntry


def _create_wav(path: str, duration: float = 1.0, rate: int = 22050):
    """Crea un archivo WAV válido para testing."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    n_frames = int(rate * duration)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        for _ in range(n_frames):
            wf.writeframes(struct.pack("<h", 0))


class MockTTSService:
    async def synthesize(self, text: str) -> bytes:
        return b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x22\x56\x00\x00\x22\x56\x00\x00\x01\x00\x08\x00data\x04\x00\x00\x00\x00\x00\x00\x00"


class TestSoundCache:
    @pytest.fixture
    def audio_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield d

    def test_init_empty_directory(self, audio_dir):
        sc = SoundCache(audio_dir=audio_dir)
        assert sc.reindex() == 0

    def test_index_wav(self, audio_dir):
        _create_wav(os.path.join(audio_dir, "test.wav"), duration=0.5)
        sc = SoundCache(audio_dir=audio_dir)
        assert sc.exists("test")

    def test_index_nested_category(self, audio_dir):
        _create_wav(os.path.join(audio_dir, "fuel", "critical.wav"), duration=0.3)
        sc = SoundCache(audio_dir=audio_dir)
        assert sc.exists("fuel/critical")
        assert "fuel" in sc.list_categories()

    def test_get_returns_entry(self, audio_dir):
        _create_wav(os.path.join(audio_dir, "spotter", "clear.wav"), duration=0.2)
        sc = SoundCache(audio_dir=audio_dir)
        entry = sc.get("spotter/clear")
        assert entry is not None
        assert entry.name == "spotter/clear"
        assert entry.category == "spotter"
        assert entry.duration > 0

    def test_get_miss_no_tts(self, audio_dir):
        sc = SoundCache(audio_dir=audio_dir)
        entry = sc.get("nonexistent")
        assert entry is None

    def test_get_miss_with_tts(self, audio_dir):
        sc = SoundCache(audio_dir=audio_dir, tts_service=MockTTSService())
        entry = sc.get("fuel/critical")
        assert entry is not None
        assert sc.exists("fuel/critical")

    def test_reindex(self, audio_dir):
        sc = SoundCache(audio_dir=audio_dir)
        assert sc.reindex() == 0
        _create_wav(os.path.join(audio_dir, "new.wav"))
        assert sc.reindex() == 1

    def test_list_categories(self, audio_dir):
        _create_wav(os.path.join(audio_dir, "fuel", "low.wav"))
        _create_wav(os.path.join(audio_dir, "tyre", "hot.wav"))
        sc = SoundCache(audio_dir=audio_dir)
        cats = sc.list_categories()
        assert "fuel" in cats
        assert "tyre" in cats
