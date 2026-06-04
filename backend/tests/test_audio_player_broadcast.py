"""Tests for AudioPlayer broadcast callback behavior."""
import time
from unittest.mock import MagicMock

import pytest

from src.models.messages import QueuedMessage
from src.services.audio_player import AudioPlayer, NullAudioOutput
from src.services.sound_cache import SoundCache, SoundEntry


@pytest.fixture
def mock_cache():
    """Mock SoundCache that returns a valid SoundEntry."""
    cache = MagicMock(spec=SoundCache)
    cache.get.return_value = SoundEntry(name="test", path="fake.wav", category="test", duration=1.0)
    return cache


def test_broadcast_called_when_callback_set(mock_cache):
    """Broadcast callback should be called once when a message is processed."""
    mock_callback = MagicMock()
    player = AudioPlayer(
        sound_cache=mock_cache,
        broadcast_callback=mock_callback,
        audio_output=NullAudioOutput(),
    )
    msg = QueuedMessage(name="test_broadcast", priority=10)
    player.play(msg)
    player.start()
    time.sleep(0.3)
    player.stop()

    mock_callback.assert_called_once_with(msg)


def test_broadcast_not_called_when_callback_none(mock_cache):
    """No broadcast callback means no broadcast -- no exception should occur."""
    player = AudioPlayer(
        sound_cache=mock_cache,
        broadcast_callback=None,
        audio_output=NullAudioOutput(),
    )
    msg = QueuedMessage(name="test_no_broadcast", priority=10)
    player.play(msg)
    player.start()
    time.sleep(0.3)
    player.stop()
    # Test passes if no exception is raised


def test_broadcast_exception_does_not_crash(mock_cache):
    """An exception inside the broadcast callback must be caught, not crash the player."""

    def failing_callback(msg):
        raise RuntimeError("boom")

    player = AudioPlayer(
        sound_cache=mock_cache,
        broadcast_callback=failing_callback,
        audio_output=NullAudioOutput(),
    )
    msg = QueuedMessage(name="test_exception", priority=10)
    player.play(msg)
    player.start()
    time.sleep(0.3)
    player.stop()
    # Test passes if no exception propagates to the test