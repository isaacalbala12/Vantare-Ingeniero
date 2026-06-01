"""Índice de archivos de audio WAV con generación bajo demanda.

Escanea backend/audio/ para construir un índice de WAVs disponibles.
Si un WAV no existe, lo genera usando el TTS configurado (Edge TTS por defecto)
y lo guarda para futuros usos.
"""

import os
import wave
import logging
import threading
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger("vantare.sound_cache")


class SoundEntry:
    __slots__ = ("name", "path", "category", "duration")

    def __init__(self, name: str, path: str, category: str = "", duration: float = 0.0):
        self.name = name
        self.path = path
        self.category = category
        self.duration = duration


class SoundCache:
    """Índice de WAVs con generación bajo demanda. Thread-safe."""

    def __init__(self, audio_dir: Optional[str] = None, tts_service=None):
        self._lock = threading.Lock()
        self._index: Dict[str, SoundEntry] = {}
        self._tts = tts_service
        self._audio_dir = audio_dir or self._default_audio_dir()
        self._reindex()

    @staticmethod
    def _default_audio_dir() -> str:
        """Devuelve la ruta por defecto backend/audio/."""
        import sys, os
        if hasattr(sys, "_MEIPASS"):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "audio")

    def _reindex(self) -> None:
        """Escanea el directorio de audio y reconstruye el índice."""
        self._index.clear()
        audio_path = Path(self._audio_dir)
        if not audio_path.exists():
            audio_path.mkdir(parents=True, exist_ok=True)
            logger.info("Created audio directory: %s", self._audio_dir)
            return

        for wav_path in audio_path.rglob("*.wav"):
            try:
                rel = wav_path.relative_to(audio_path)
                name = rel.with_suffix("").as_posix()
                with wave.open(str(wav_path), "r") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    duration = frames / rate if rate > 0 else 0.0
                category = rel.parent.as_posix() if rel.parent.as_posix() != "." else ""
                self._index[name] = SoundEntry(
                    name=name,
                    path=str(wav_path),
                    category=category,
                    duration=duration,
                )
            except (wave.Error, OSError, ValueError) as e:
                logger.warning("Skipping invalid WAV %s: %s", wav_path, e)

        logger.info("SoundCache: indexed %d WAV files from %s", len(self._index), self._audio_dir)

    def get(self, name: str) -> Optional[SoundEntry]:
        """Devuelve el SoundEntry si existe. Thread-safe."""
        with self._lock:
            entry = self._index.get(name)
            if entry is not None:
                return entry
        # Cache miss: generar bajo demanda
        if self._tts is not None:
            return self._generate(name)
        logger.warning("SoundCache miss: '%s' not found and no TTS service available", name)
        return None

    def _generate(self, name: str) -> Optional[SoundEntry]:
        """Genera un WAV usando TTS y lo añade al índice."""
        import asyncio
        category, _, leaf = name.rpartition("/")
        text = leaf.replace("_", " ").replace("-", " ")
        try:
            audio_bytes = asyncio.run(self._tts.synthesize(text))
        except Exception as e:
            logger.error("SoundCache TTS generate failed for '%s': %s", name, e)
            return None
        audio_path = Path(self._audio_dir) / f"{name}.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            audio_path.write_bytes(audio_bytes)
        except OSError as e:
            logger.error("SoundCache write failed for '%s': %s", name, e)
            return None
        try:
            import wave
            with wave.open(str(audio_path), "r") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / rate if rate > 0 else 0.0
        except (wave.Error, OSError):
            duration = 0.0
        entry = SoundEntry(name=name, path=str(audio_path), category=category, duration=duration)
        with self._lock:
            self._index[name] = entry
        logger.info("SoundCache: generated '%s' via TTS -> %s", name, audio_path)
        return entry

    def exists(self, name: str) -> bool:
        """Verifica si un WAV existe en el índice."""
        with self._lock:
            return name in self._index

    def reindex(self) -> int:
        """Reconstruye el índice (útil tras generar WAVs desde admin)."""
        with self._lock:
            self._reindex()
        return len(self._index)

    def list_categories(self) -> list:
        """Devuelve lista de categorías disponibles."""
        with self._lock:
            cats = set()
            for entry in self._index.values():
                if entry.category:
                    cats.add(entry.category)
            return sorted(cats)
