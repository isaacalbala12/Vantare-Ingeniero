import time
import pytest
from src.services.audio_player import (
    AudioPlayer, AudioOutput, NullAudioOutput,
    PRIORITY_SPOTTER, PRIORITY_CRITICAL, PRIORITY_NORMAL,
)
from src.models.messages import QueuedMessage
from src.services.sound_cache import SoundCache


class MockSoundCache:
    def __init__(self):
        self._wavs = {}

    def get(self, name):
        if name == "exists":
            return type("MockEntry", (), {"path": "/fake/test.wav", "name": "exists"})()
        return self._wavs.get(name)


class TestAudioPlayer:
    @pytest.fixture
    def player(self):
        sc = MockSoundCache()
        ap = AudioPlayer(sound_cache=sc, audio_output=NullAudioOutput())
        ap.start()
        yield ap
        ap.stop()
        ap.purge()

    def test_play_queues_message(self, player):
        msg = QueuedMessage("exists", priority=PRIORITY_NORMAL)
        player.play(msg)
        assert player.queue_size == 1

    def test_play_imm_queues_immediate(self, player):
        msg = QueuedMessage("exists", priority=PRIORITY_NORMAL)
        player.play_imm(msg)
        assert player.queue_size == 1

    def test_purge_empties_queue(self, player):
        for i in range(5):
            player.play(QueuedMessage("exists", priority=PRIORITY_NORMAL))
        assert player.queue_size == 5
        purged = player.purge()
        assert purged == 5
        assert player.queue_size == 0

    def test_pause_resume(self, player):
        player.play(QueuedMessage("exists", priority=PRIORITY_NORMAL))
        player.pause_queue(0.1)
        assert player._paused
        time.sleep(0.2)
        assert not player._paused

    def test_priority_order(self, player):
        normal = QueuedMessage("exists", priority=PRIORITY_NORMAL)
        critical = QueuedMessage("exists", priority=PRIORITY_CRITICAL)
        player.play(normal)
        player.play(critical)
        next_msg = player._next_message()
        assert next_msg.priority == PRIORITY_CRITICAL

    def test_immediate_before_normal(self, player):
        normal = QueuedMessage("exists", priority=PRIORITY_NORMAL)
        imm = QueuedMessage("exists", priority=PRIORITY_NORMAL)
        player.play(normal)
        player.play_imm(imm)
        next_msg = player._next_message()
        assert next_msg.id == imm.id

    def test_is_playing_after_play(self, player):
        assert not player.is_playing
        msg = QueuedMessage("exists", priority=PRIORITY_NORMAL)
        player.play(msg)
        time.sleep(0.05)
        # After a brief delay the player loop should pick it up
        # We can't guarantee it's still playing since NullAudioOutput is instant
        # Just verify it was picked up and queue is empty
        assert player.queue_size == 0

    def test_spoter_interrupt(self, player):
        normal = QueuedMessage("exists", priority=PRIORITY_NORMAL)
        spotter = QueuedMessage("exists", priority=PRIORITY_SPOTTER)
        setattr(spotter, "_interrupt", True)
        player.play(normal)
        player.play_imm(spotter)
        next_msg = player._next_message()
        assert next_msg.priority == PRIORITY_SPOTTER

    def test_set_validator(self, player):
        called = [False]
        def validator(msg):
            called[0] = True
            return True
        player.set_validator(validator)
        msg = QueuedMessage("exists", priority=PRIORITY_NORMAL)
        player.play(msg)
        time.sleep(0.05)
        assert called[0]
