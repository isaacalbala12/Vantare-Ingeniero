"""Reproductor de audio con cola dual de prioridades y reproducción en hilo separado.

Cola normal: FIFO dentro de cada nivel de prioridad (5 niveles).
Cola inmediata: siempre se reproduce antes que la normal.
Spotter (prioridad 20): puede interrumpir la reproducción actual si tiene flag interrupt=True.
"""

import os
import wave
import time
import logging
import threading
from typing import Optional, Callable, Dict
from collections import OrderedDict

from src.models.messages import QueuedMessage
from src.services.sound_cache import SoundCache

logger = logging.getLogger("vantare.audio_player")

PRIORITY_SPOTTER = 20
PRIORITY_CRITICAL = 15
PRIORITY_IMPORTANT = 10
PRIORITY_VOICE = 8
PRIORITY_NORMAL = 5


class AudioOutput:
    """Interfaz de salida de audio. Intercambiable para testing."""

    def play_wav(self, path: str, stop_flag: threading.Event) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class PyAudioOutput(AudioOutput):
    """Salida de audio real usando PyAudio."""

    def __init__(self):
        self._py_audio = None
        self._owned_output: bool = False

    def play_wav(self, path: str, stop_flag: threading.Event) -> None:
        if not os.path.exists(path):
            logger.warning("WAV not found: %s", path)
            return
        try:
            wf = wave.open(path, "rb")
        except (wave.Error, OSError) as e:
            logger.error("Failed to open WAV %s: %s", path, e)
            return
        try:
            if self._py_audio is None:
                self._py_audio = pyaudio.PyAudio()
            stream = self._py_audio.open(
                format=self._py_audio.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
            )
            chunk_size = 1024
            data = wf.readframes(chunk_size)
            while data and not stop_flag.is_set():
                stream.write(data)
                data = wf.readframes(chunk_size)
            stream.stop_stream()
            stream.close()
        except Exception as e:
            logger.error("Audio playback error: %s", e)
        finally:
            wf.close()

    def close(self) -> None:
        if hasattr(self, '_py_audio') and self._py_audio:
            self._py_audio.terminate()
            self._py_audio = None


class NullAudioOutput(AudioOutput):
    """Salida nula para testing. Solo loggea."""

    def play_wav(self, path: str, stop_flag: threading.Event) -> None:
        logger.debug("NullAudioOutput: would play %s", path)


class AudioPlayer:
    """Reproductor con cola dual. Usa ThreadPoolExecutor para no bloquear el event loop."""

    def __init__(self, sound_cache: SoundCache, broadcast_callback: Optional[Callable] = None,
                 audio_output: Optional[AudioOutput] = None):
        self._cache = sound_cache
        self._broadcast = broadcast_callback
        # Cola normal: OrderedDict anidado {priority: OrderedDict{msg_id: QueuedMessage}}
        self._queue: Dict[int, OrderedDict] = {p: OrderedDict() for p in
                                                [PRIORITY_SPOTTER, PRIORITY_CRITICAL,
                                                 PRIORITY_IMPORTANT, PRIORITY_VOICE, PRIORITY_NORMAL]}
        # Cola inmediata: siempre se reproduce antes
        self._immediate: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self._executor = None
        self._current: Optional[QueuedMessage] = None
        self._paused = False
        self._stop_flag = threading.Event()
        self._player_thread: Optional[threading.Thread] = None
        self._running = False
        self._audio_output = audio_output
        self._owned_output = audio_output is None
        self._is_message_still_valid: Optional[Callable[[QueuedMessage], bool]] = None

    def set_validator(self, validator: Callable[[QueuedMessage], bool]) -> None:
        """Registra un callback que valida si un mensaje sigue siendo relevante antes de reproducirlo."""
        self._is_message_still_valid = validator

    def play(self, msg: QueuedMessage) -> None:
        """Añade un mensaje a la cola normal. Thread-safe."""
        with self._lock:
            prio = msg.priority
            if prio not in self._queue:
                prio = PRIORITY_NORMAL
            self._queue[prio][msg.id] = msg
            logger.debug("AudioPlayer queued (prio=%d): %s", prio, msg.name)

    def play_imm(self, msg: QueuedMessage) -> None:
        """Añade un mensaje a la cola inmediata. Thread-safe."""
        with self._lock:
            self._immediate[msg.id] = msg
            # Si hay reproducción actual y el nuevo mensaje es spotter con interrupt
            if msg.priority >= PRIORITY_SPOTTER and self._current is not None:
                if getattr(msg, "_interrupt", False):
                    self._stop_flag.set()
            logger.debug("AudioPlayer immediate queued: %s", msg.name)

    def purge(self) -> int:
        """Vacía todas las colas. Devuelve número de mensajes eliminados."""
        with self._lock:
            total = 0
            for prio in self._queue:
                total += len(self._queue[prio])
                self._queue[prio].clear()
            total += len(self._immediate)
            self._immediate.clear()
            if total > 0:
                logger.info("AudioPlayer purged %d messages", total)
            return total

    def pause_queue(self, seconds: float) -> None:
        """Pausa la reproducción durante N segundos (útil durante FCY)."""
        self._paused = True
        logger.info("AudioPlayer paused for %.1fs", seconds)

        def _resume():
            time.sleep(seconds)
            self._paused = False
            logger.info("AudioPlayer resumed after %.1fs", seconds)

        threading.Thread(target=_resume, daemon=True).start()

    @property
    def is_playing(self) -> bool:
        return self._current is not None

    @property
    def queue_size(self) -> int:
        with self._lock:
            return sum(len(q) for q in self._queue.values()) + len(self._immediate)

    def _next_message(self) -> Optional[QueuedMessage]:
        """Saca el siguiente mensaje de las colas (inmediata primero)."""
        with self._lock:
            # Cola inmediata primero
            if self._immediate:
                _, msg = self._immediate.popitem(last=False)
                return msg
            # Cola normal por prioridad descendente
            for prio in sorted(self._queue.keys(), reverse=True):
                q = self._queue[prio]
                if q:
                    _, msg = q.popitem(last=False)
                    return msg
            return None

    def _ensure_audio_output(self) -> AudioOutput:
        """Devuelve la salida de audio, creando PyAudioOutput si es necesario."""
        if self._audio_output is None:
            self._audio_output = PyAudioOutput()
            self._owned_output = True
        return self._audio_output

    def _player_loop(self) -> None:
        """Bucle interno de reproducción. Corre en su propio hilo."""
        self._running = True
        while self._running:
            if self._paused:
                time.sleep(0.1)
                continue
            msg = self._next_message()
            if msg is None:
                time.sleep(0.05)
                continue
            self._current = msg
            self._stop_flag.clear()
            # Validar que el mensaje sigue siendo relevante
            if self._is_message_still_valid and not self._is_message_still_valid(msg):
                self._current = None
                continue
            # Obtener el WAV
            entry = self._cache.get(msg.name)
            if entry is None:
                logger.warning("No audio available for: %s", msg.name)
                self._current = None
                continue
            # Broadcast del mensaje
            if self._broadcast:
                logger.debug("Broadcasting crewchief event: %s", msg.name if hasattr(msg, 'name') else '?')
                try:
                    self._broadcast(msg)
                except Exception as e:
                    logger.error("Broadcast failed: %s", e)
            # Reproducir
            output = self._ensure_audio_output()
            output.play_wav(entry.path, self._stop_flag)
            self._current = None
        self._running = False

    def start(self) -> None:
        """Inicia el hilo de reproducción."""
        if self._player_thread is not None and self._player_thread.is_alive():
            logger.warning("AudioPlayer already running")
            return
        self._stop_flag.clear()
        self._running = True
        self._player_thread = threading.Thread(target=self._player_loop, daemon=True, name="audio-player")
        self._player_thread.start()
        logger.info("AudioPlayer started")

    def stop(self) -> None:
        """Detiene el hilo de reproducción."""
        self._running = False
        self._stop_flag.set()
        if self._player_thread and self._player_thread.is_alive():
            self._player_thread.join(timeout=2.0)
        if self._owned_output and self._audio_output:
            self._audio_output.close()
            self._audio_output = None
        logger.info("AudioPlayer stopped")
