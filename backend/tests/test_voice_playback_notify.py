from src.models.messages import VoicePlaybackEndMessage, VoicePlaybackStartMessage
from src.voice.playback_notify import VoicePlaybackNotifier, derive_playback_source
from src.voice.play_command import PlayCommand
import time


def _cmd(**overrides) -> PlayCommand:
    base = dict(
        id="play-1",
        text="Coche a la izquierda",
        priority="IMMEDIATE",
        category="proximity",
        event_id="proximity_left",
        ttl_ms=5000,
        expires_at=time.monotonic() + 5,
    )
    base.update(overrides)
    return PlayCommand(**base)


def test_derive_playback_source():
    assert derive_playback_source("proximity") == "spotter"
    assert derive_playback_source("voice_response") == "engineer"


def test_notifier_emits_start_and_end():
    sent: list = []

    notifier = VoicePlaybackNotifier(sent.append)
    cmd = _cmd()
    playback_id = notifier.notify_start(cmd)
    assert playback_id == "play-1"
    assert len(sent) == 1
    start = sent[0]
    assert isinstance(start, VoicePlaybackStartMessage)
    assert start.event == "voice_playback_start"
    assert start.text == cmd.text
    assert start.source == "spotter"

    notifier.notify_end(playback_id)
    assert len(sent) == 2
    end = sent[1]
    assert isinstance(end, VoicePlaybackEndMessage)
    assert end.playback_id == "play-1"
