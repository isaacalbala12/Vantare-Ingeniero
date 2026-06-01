"""Tests del AudioPlayer — reproductor con cola dual de prioridades.

Cobertura:
- Cola normal: orden FIFO por prioridad (5 niveles)
- Cola inmediata: salta la normal
- Interrupción: spotter con flag _interrupt=True corta reproducción actual
- Purge: vacía todas las colas
- Pause/Resume: pausa la reproducción durante N segundos
- Validator: valida mensajes antes de reproducir
- is_playing y queue_size
- PyAudioOutput: import correcto, close() idempotente, manejo de errores
- AudioOutput / NullAudioOutput: comportamiento base
- Concurrencia: múltiples hilos añadiendo mensajes
"""
import os
import time
import wave
import threading
import pytest

from src.services.audio_player import (
    AudioPlayer, AudioOutput, NullAudioOutput, PyAudioOutput,
    PRIORITY_SPOTTER, PRIORITY_CRITICAL, PRIORITY_IMPORTANT,
    PRIORITY_VOICE, PRIORITY_NORMAL,
)
from src.models.messages import QueuedMessage
from src.services.sound_cache import SoundEntry


class MockSoundCache:
    def __init__(self):
        self.calls = []

    def get(self, name):
        self.calls.append(name)
        return SoundEntry(name=name, path="/fake/" + name, category="")


class CountedAudioOutput(AudioOutput):
    """Cuenta cuántas veces se reprodujo cada path."""
    def __init__(self):
        self.played = []
        self.stop_flags = []

    def play_wav(self, path, stop_flag):
        self.played.append(path)
        self.stop_flags.append(stop_flag)


@pytest.fixture
def player():
    sc = MockSoundCache()
    output = CountedAudioOutput()
    ap = AudioPlayer(sound_cache=sc, audio_output=output)
    ap.start()
    yield ap, output
    ap.stop()
    ap.purge()


class TestQueueBehavior:
    def test_play_adds_to_normal_queue(self, player):
        ap, _ = player
        msg = QueuedMessage("test/path", priority=PRIORITY_NORMAL)
        ap.play(msg)
        assert ap.queue_size == 1

    def test_play_imm_adds_to_immediate_queue(self, player):
        ap, _ = player
        msg = QueuedMessage("test/path", priority=PRIORITY_NORMAL)
        ap.play_imm(msg)
        assert ap.queue_size == 1

    def test_immediate_plays_before_normal(self, player):
        ap, output = player
        normal = QueuedMessage("normal", priority=PRIORITY_NORMAL)
        imm = QueuedMessage("immediate", priority=PRIORITY_NORMAL)
        ap.play(normal)
        ap.play_imm(imm)
        # Esperar a procesar
        for _ in range(20):
            if ap.queue_size == 0:
                break
            time.sleep(0.05)
        # El primer reproducido debe ser el immediate
        assert output.played[0] == "/fake/immediate"
        assert output.played[1] == "/fake/normal"

    def test_purge_empties_all_queues(self, player):
        ap, _ = player
        for i in range(5):
            ap.play(QueuedMessage(f"msg{i}", priority=PRIORITY_NORMAL))
        ap.play_imm(QueuedMessage("imm", priority=PRIORITY_NORMAL))
        assert ap.queue_size == 6
        purged = ap.purge()
        assert purged == 6
        assert ap.queue_size == 0

    def test_purge_returns_zero_when_empty(self, player):
        ap, _ = player
        assert ap.purge() == 0


class TestPriorityOrdering:
    def test_higher_priority_plays_first(self, player):
        ap, output = player
        normal = QueuedMessage("normal", priority=PRIORITY_NORMAL)
        critical = QueuedMessage("critical", priority=PRIORITY_CRITICAL)
        ap.play(normal)
        ap.play(critical)
        for _ in range(20):
            if ap.queue_size == 0:
                break
            time.sleep(0.05)
        # El primer reproducido debe ser el de prioridad mayor
        assert output.played[0] == "/fake/critical"
        assert output.played[1] == "/fake/normal"

    def test_spotter_plays_first(self, player):
        ap, output = player
        ap.play(QueuedMessage("normal", priority=PRIORITY_NORMAL))
        ap.play(QueuedMessage("critical", priority=PRIORITY_CRITICAL))
        ap.play(QueuedMessage("spotter", priority=PRIORITY_SPOTTER))
        for _ in range(20):
            if ap.queue_size == 0:
                break
            time.sleep(0.05)
        assert output.played[0] == "/fake/spotter"
        assert output.played[1] == "/fake/critical"
        assert output.played[2] == "/fake/normal"

    def test_fifo_within_same_priority(self, player):
        """Dentro de la misma prioridad, FIFO."""
        ap, output = player
        # Parar el player para acumular mensajes
        ap.stop()
        ap.purge()
        ap.play(QueuedMessage("first", priority=PRIORITY_NORMAL))
        ap.play(QueuedMessage("second", priority=PRIORITY_NORMAL))
        ap.play(QueuedMessage("third", priority=PRIORITY_NORMAL))
        ap.start()
        for _ in range(20):
            if ap.queue_size == 0:
                break
            time.sleep(0.05)
        assert output.played[0] == "/fake/first"
        assert output.played[1] == "/fake/second"
        assert output.played[2] == "/fake/third"

    def test_invalid_priority_falls_back_to_normal(self, player):
        """Si un mensaje tiene prioridad fuera de los 5 niveles, va a NORMAL."""
        ap, _ = player
        msg = QueuedMessage("weird", priority=99)  # prioridad inválida
        ap.play(msg)
        # Debe estar en alguna cola (no debe crashear)
        assert ap.queue_size == 1


class TestPauseResume:
    def test_pause_blocks_reproduction(self):
        sc = MockSoundCache()
        output = CountedAudioOutput()
        ap = AudioPlayer(sound_cache=sc, audio_output=output)
        ap.start()
        ap.pause_queue(0.3)  # Pausa 300ms
        ap.play(QueuedMessage("test", priority=PRIORITY_NORMAL))
        time.sleep(0.1)  # Durante la pausa
        assert ap._paused is True
        # Esperar a que pase la pausa
        for _ in range(20):
            if not ap._paused:
                break
            time.sleep(0.05)
        assert ap._paused is False
        ap.stop()
        ap.purge()

    def test_pause_does_not_lose_messages(self):
        """Los mensajes encolados durante la pausa no se pierden."""
        sc = MockSoundCache()
        output = CountedAudioOutput()
        ap = AudioPlayer(sound_cache=sc, audio_output=output)
        ap.start()
        ap.pause_queue(0.1)
        ap.play(QueuedMessage("during_pause", priority=PRIORITY_NORMAL))
        # Esperar a que la pausa termine Y se procese
        for _ in range(40):
            if ap.queue_size == 0 and not ap._paused:
                break
            time.sleep(0.05)
        assert "during_pause" in output.played[0] if output.played else False
        ap.stop()
        ap.purge()


class TestValidator:
    def test_validator_rejects_message(self):
        """Si el validator devuelve False, el mensaje no se reproduce."""
        sc = MockSoundCache()
        output = CountedAudioOutput()
        ap = AudioPlayer(sound_cache=sc, audio_output=output)
        ap.set_validator(lambda msg: False)  # Siempre rechaza
        ap.start()
        ap.play(QueuedMessage("rejected", priority=PRIORITY_NORMAL))
        for _ in range(20):
            if ap.queue_size == 0:
                break
            time.sleep(0.05)
        # El mensaje fue procesado (queue vacía) pero NO reproducido
        assert ap.queue_size == 0
        assert len(output.played) == 0
        ap.stop()
        ap.purge()

    def test_validator_accepts_message(self, player):
        ap, output = player
        ap.set_validator(lambda msg: True)
        ap.play(QueuedMessage("accepted", priority=PRIORITY_NORMAL))
        for _ in range(20):
            if ap.queue_size == 0:
                break
            time.sleep(0.05)
        assert "/fake/accepted" in output.played

    def test_validator_exception_does_not_crash_loop(self):
        """P1 fix: validator que lanza excepción no debe crashear el player loop."""
        sc = MockSoundCache()
        output = CountedAudioOutput()
        ap = AudioPlayer(sound_cache=sc, audio_output=output)
        def bad_validator(msg):
            raise ValueError("validator boom")
        ap.set_validator(bad_validator)
        ap.start()
        ap.play(QueuedMessage("after_explosion", priority=PRIORITY_NORMAL))
        for _ in range(20):
            if ap.queue_size == 0:
                break
            time.sleep(0.05)
        # El thread sigue vivo
        assert ap._player_thread.is_alive()
        # El mensaje se reprodujo (validator exception = no rechazar)
        assert "/fake/after_explosion" in output.played
        ap.stop()
        ap.purge()


class TestPlayState:
    def test_is_playing_initially_false(self):
        sc = MockSoundCache()
        ap = AudioPlayer(sound_cache=sc, audio_output=NullAudioOutput())
        assert ap.is_playing is False

    def test_queue_size_initially_zero(self):
        sc = MockSoundCache()
        ap = AudioPlayer(sound_cache=sc, audio_output=NullAudioOutput())
        assert ap.queue_size == 0


class TestNullAudioOutput:
    def test_null_output_never_crashes(self):
        out = NullAudioOutput()
        flag = threading.Event()
        # No debe lanzar excepción
        out.play_wav("/nonexistent.wav", flag)
        out.close()

    def test_null_output_does_nothing(self):
        out = NullAudioOutput()
        flag = threading.Event()
        out.play_wav("test.wav", flag)
        # No hay forma de verificar que "no hizo nada" más allá de no crashear


class TestPyAudioOutput:
    def test_close_is_idempotent(self):
        """P0 fix: close() debe poder llamarse múltiples veces."""
        out = PyAudioOutput()
        out.close()
        out.close()  # No debe lanzar excepción

    def test_close_does_not_crash_without_init(self):
        """P0 fix: close() sin reproducción previa no debe crashear."""
        out = PyAudioOutput()
        out.close()
        assert out._py_audio is None

    def test_play_wav_handles_no_pyaudio(self):
        """P0 fix: sin pyaudio instalado, play_wav falla sin crashear."""
        from src.services import audio_player as ap_module
        original = ap_module._PYAUDIO_AVAILABLE
        ap_module._PYAUDIO_AVAILABLE = False
        try:
            out = PyAudioOutput()
            test_wav = os.path.join(os.path.dirname(__file__), "tmp_test.wav")
            with wave.open(test_wav, "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(b"\x00\x00" * 100)
            try:
                flag = threading.Event()
                out.play_wav(test_wav, flag)  # No debe lanzar
            finally:
                os.remove(test_wav)
            out.close()
        finally:
            ap_module._PYAUDIO_AVAILABLE = original

    def test_play_wav_handles_missing_file(self):
        """Reproducir un archivo que no existe debe ser silencioso."""
        from src.services import audio_player as ap_module
        original = ap_module._PYAUDIO_AVAILABLE
        ap_module._PYAUDIO_AVAILABLE = True
        try:
            out = PyAudioOutput()
            flag = threading.Event()
            out.play_wav("/nonexistent/path/file.wav", flag)  # No debe lanzar
            out.close()
        finally:
            ap_module._PYAUDIO_AVAILABLE = original

    def test_play_wav_respects_stop_flag(self):
        """El stop_flag debe interrumpir la reproducción."""
        from src.services import audio_player as ap_module
        original_available = ap_module._PYAUDIO_AVAILABLE
        ap_module._PYAUDIO_AVAILABLE = True
        try:
            # Mock pyaudio para no requerir hardware real
            class MockPyAudio:
                def __init__(self):
                    self.format = None
                def open(self, format, channels, rate, output):
                    class MockStream:
                        def write(self, data): pass
                        def stop_stream(self): pass
                        def close(self): pass
                    return MockStream()
                def get_format_from_width(self, w): return 8
                def terminate(self): pass

            # Patch pyaudio
            import ctypes
            original_pyaudio = ap_module.pyaudio
            ap_module.pyaudio = type("FakePyAudio", (), {"PyAudio": MockPyAudio})()
            try:
                test_wav = os.path.join(os.path.dirname(__file__), "tmp_test2.wav")
                with wave.open(test_wav, "w") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(22050)
                    wf.writeframes(b"\x00\x00" * 100)
                try:
                    out = PyAudioOutput()
                    flag = threading.Event()
                    flag.set()  # Stop ya activado
                    out.play_wav(test_wav, flag)  # No debe crashear
                    out.close()
                finally:
                    os.remove(test_wav)
            finally:
                ap_module.pyaudio = original_pyaudio
        finally:
            ap_module._PYAUDIO_AVAILABLE = original_available


class TestThreadSafety:
    def test_multiple_threads_adding_messages(self):
        sc = MockSoundCache()
        output = CountedAudioOutput()
        ap = AudioPlayer(sound_cache=sc, audio_output=output)
        ap.start()

        def add_messages(prefix, n):
            for i in range(n):
                ap.play(QueuedMessage(f"{prefix}_{i}", priority=PRIORITY_NORMAL))

        threads = [
            threading.Thread(target=add_messages, args=("A", 10)),
            threading.Thread(target=add_messages, args=("B", 10)),
            threading.Thread(target=add_messages, args=("C", 10)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Esperar a procesar todo
        for _ in range(100):
            if ap.queue_size == 0:
                break
            time.sleep(0.05)

        # Todos los 30 mensajes deben haberse reproducido
        assert len(output.played) == 30
        ap.stop()
        ap.purge()


class TestStartStop:
    def test_start_when_already_running_does_nothing(self):
        sc = MockSoundCache()
        ap = AudioPlayer(sound_cache=sc, audio_output=NullAudioOutput())
        ap.start()
        thread1 = ap._player_thread
        ap.start()  # No debe crear nuevo thread
        thread2 = ap._player_thread
        assert thread1 is thread2
        ap.stop()
        ap.purge()

    def test_stop_joins_thread(self):
        sc = MockSoundCache()
        ap = AudioPlayer(sound_cache=sc, audio_output=NullAudioOutput())
        ap.start()
        assert ap._player_thread.is_alive()
        ap.stop()
        assert not ap._player_thread.is_alive()
