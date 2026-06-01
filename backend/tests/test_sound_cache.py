"""Tests del SoundCache — índice de WAVs con generación bajo demanda.

Cobertura:
- Init: directorio vacío, directorio con WAVs, directorio inexistente
- Indexing: WAV simple, categorías anidadas, WAVs corruptos ignorados
- get(): cache hit, cache miss sin TTS, cache miss con TTS
- Generación bajo demanda: genera WAV, lo guarda, lo añade al índice
- exists(): existencia en índice
- reindex(): reconstrucción completa
- list_categories(): categorías únicas
- Concurrencia: dos hilos pidiendo cache miss solo generan una vez
- Race conditions: get() con generación en curso
"""
import os
import tempfile
import wave
import struct
import pytest
import asyncio
from threading import Thread
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


def _create_corrupt_wav(path: str):
    """Crea un archivo que parece WAV pero está corrupto."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"NOT_A_REAL_WAV_FILE")


class MockTTSService:
    """Mock del servicio TTS que devuelve bytes WAV válidos."""
    def __init__(self):
        self.call_count = 0
        self.calls = []

    async def synthesize(self, text: str) -> bytes:
        self.call_count += 1
        self.calls.append(text)
        # Devuelve un WAV mínimo válido
        import io
        buf = io.BytesIO()
        with wave.open(buf, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(22050)
            wf.writeframes(b"\x00\x00" * 100)
        return buf.getvalue()


class TestInit:
    def test_init_empty_directory(self):
        with tempfile.TemporaryDirectory() as d:
            sc = SoundCache(audio_dir=d)
            assert sc.reindex() == 0

    def test_init_nonexistent_directory_creates_it(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "new_audio")
            assert not os.path.exists(target)
            sc = SoundCache(audio_dir=target)
            assert os.path.exists(target)

    def test_init_with_existing_wav(self):
        with tempfile.TemporaryDirectory() as d:
            _create_wav(os.path.join(d, "test.wav"), duration=0.5)
            sc = SoundCache(audio_dir=d)
            assert sc.reindex() == 1
            assert sc.exists("test")


class TestIndexing:
    def test_indexes_wav(self):
        with tempfile.TemporaryDirectory() as d:
            _create_wav(os.path.join(d, "spotter.wav"), duration=0.3)
            sc = SoundCache(audio_dir=d)
            assert sc.exists("spotter")

    def test_indexes_nested_categories(self):
        with tempfile.TemporaryDirectory() as d:
            _create_wav(os.path.join(d, "fuel", "critical.wav"), duration=0.3)
            _create_wav(os.path.join(d, "tyre", "hot.wav"), duration=0.3)
            sc = SoundCache(audio_dir=d)
            assert sc.exists("fuel/critical")
            assert sc.exists("tyre/hot")

    def test_skips_corrupt_wav(self):
        with tempfile.TemporaryDirectory() as d:
            _create_wav(os.path.join(d, "valid.wav"))
            _create_corrupt_wav(os.path.join(d, "corrupt.wav"))
            sc = SoundCache(audio_dir=d)
            assert sc.exists("valid")
            assert not sc.exists("corrupt")

    def test_duration_is_calculated(self):
        with tempfile.TemporaryDirectory() as d:
            _create_wav(os.path.join(d, "test.wav"), duration=2.0)
            sc = SoundCache(audio_dir=d)
            entry = sc.get("test")
            assert entry is not None
            assert 1.9 < entry.duration < 2.1

    def test_category_is_extracted(self):
        with tempfile.TemporaryDirectory() as d:
            _create_wav(os.path.join(d, "fuel", "critical.wav"))
            sc = SoundCache(audio_dir=d)
            entry = sc.get("fuel/critical")
            assert entry.category == "fuel"

    def test_top_level_wav_has_no_category(self):
        with tempfile.TemporaryDirectory() as d:
            _create_wav(os.path.join(d, "spotter.wav"))
            sc = SoundCache(audio_dir=d)
            entry = sc.get("spotter")
            assert entry.category == ""


class TestGet:
    def test_get_existing_returns_entry(self):
        with tempfile.TemporaryDirectory() as d:
            _create_wav(os.path.join(d, "test.wav"), duration=0.2)
            sc = SoundCache(audio_dir=d)
            entry = sc.get("test")
            assert entry is not None
            assert entry.name == "test"
            assert entry.path.endswith("test.wav")

    def test_get_miss_without_tts_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            sc = SoundCache(audio_dir=d, tts_service=None)
            entry = sc.get("nonexistent")
            assert entry is None

    def test_get_miss_with_tts_generates(self):
        with tempfile.TemporaryDirectory() as d:
            tts = MockTTSService()
            sc = SoundCache(audio_dir=d, tts_service=tts)
            entry = sc.get("fuel/critical")
            assert entry is not None
            assert tts.call_count == 1
            # El WAV debe haberse guardado en disco
            assert os.path.exists(entry.path)
            # Y debe existir ahora en el índice
            assert sc.exists("fuel/critical")

    def test_second_get_does_not_regenerate(self):
        """Si ya generamos, el segundo get() debe devolver el del índice."""
        with tempfile.TemporaryDirectory() as d:
            tts = MockTTSService()
            sc = SoundCache(audio_dir=d, tts_service=tts)
            sc.get("test")
            sc.get("test")
            sc.get("test")
            assert tts.call_count == 1


class TestExists:
    def test_exists_for_indexed(self):
        with tempfile.TemporaryDirectory() as d:
            _create_wav(os.path.join(d, "x.wav"))
            sc = SoundCache(audio_dir=d)
            assert sc.exists("x")

    def test_not_exists_for_missing(self):
        with tempfile.TemporaryDirectory() as d:
            sc = SoundCache(audio_dir=d)
            assert not sc.exists("nothing")


class TestReindex:
    def test_reindex_picks_up_new_files(self):
        with tempfile.TemporaryDirectory() as d:
            sc = SoundCache(audio_dir=d)
            assert sc.reindex() == 0
            _create_wav(os.path.join(d, "added.wav"))
            assert sc.reindex() == 1
            assert sc.exists("added")

    def test_reindex_returns_count(self):
        with tempfile.TemporaryDirectory() as d:
            _create_wav(os.path.join(d, "a.wav"))
            _create_wav(os.path.join(d, "b.wav"))
            _create_wav(os.path.join(d, "c.wav"))
            sc = SoundCache(audio_dir=d)
            assert sc.reindex() == 3


class TestListCategories:
    def test_unique_categories(self):
        with tempfile.TemporaryDirectory() as d:
            _create_wav(os.path.join(d, "fuel", "low.wav"))
            _create_wav(os.path.join(d, "fuel", "critical.wav"))
            _create_wav(os.path.join(d, "tyre", "hot.wav"))
            sc = SoundCache(audio_dir=d)
            cats = sc.list_categories()
            assert "fuel" in cats
            assert "tyre" in cats
            # Sin duplicados
            assert len(cats) == 2

    def test_empty_when_no_wavs(self):
        with tempfile.TemporaryDirectory() as d:
            sc = SoundCache(audio_dir=d)
            assert sc.list_categories() == []


class TestConcurrency:
    def test_concurrent_get_miss_generates_only_once(self):
        """P0 fix: dos hilos pidiendo el mismo cache miss no deben generar 2 veces."""
        with tempfile.TemporaryDirectory() as d:
            tts = MockTTSService()
            sc = SoundCache(audio_dir=d, tts_service=tts)

            results = [None, None]
            barrier = __import__("threading").Barrier(2)

            def worker(idx):
                barrier.wait()  # Sincronizar para empezar a la vez
                results[idx] = sc.get("fuel/critical")

            t1 = Thread(target=worker, args=(0,))
            t2 = Thread(target=worker, args=(1,))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            # El TTS solo se debió llamar UNA vez
            assert tts.call_count == 1
            assert results[0] is not None
            assert results[1] is not None
            assert results[0].name == "fuel/critical"
            assert results[1].name == "fuel/critical"

    def test_concurrent_get_different_keys(self):
        """Cache misses para claves diferentes deben generar 2 veces."""
        with tempfile.TemporaryDirectory() as d:
            tts = MockTTSService()
            sc = SoundCache(audio_dir=d, tts_service=tts)
            sc.get("a")
            sc.get("b")
            assert tts.call_count == 2

    def test_reindex_thread_safe(self):
        with tempfile.TemporaryDirectory() as d:
            sc = SoundCache(audio_dir=d)
            _create_wav(os.path.join(d, "a.wav"))

            def do_reindex():
                for _ in range(10):
                    sc.reindex()

            threads = [Thread(target=do_reindex) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            # No debe haber crasheado


class TestGenerationEdgeCases:
    def test_generates_with_underscore_to_space(self):
        """Nombres con underscores se convierten a espacios para TTS."""
        with tempfile.TemporaryDirectory() as d:
            tts = MockTTSService()
            sc = SoundCache(audio_dir=d, tts_service=tts)
            sc.get("fuel/critical_low")
            assert tts.calls == ["critical low"]

    def test_generates_with_dash_to_space(self):
        with tempfile.TemporaryDirectory() as d:
            tts = MockTTSService()
            sc = SoundCache(audio_dir=d, tts_service=tts)
            sc.get("spotter/three-wide")
            assert tts.calls == ["three wide"]

    def test_tts_failure_returns_none(self):
        """Si TTS lanza excepción, get() devuelve None sin crashear."""
        with tempfile.TemporaryDirectory() as d:
            class FailingTTS:
                async def synthesize(self, text):
                    raise RuntimeError("TTS failed")
            sc = SoundCache(audio_dir=d, tts_service=FailingTTS())
            entry = sc.get("test")
            assert entry is None
