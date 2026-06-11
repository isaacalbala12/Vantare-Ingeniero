import time

from src.voice.moderator import PlaybackModerator
from src.voice.play_command import PlayCommand


def _cmd(event_id: str, *, expires_at: float | None = None) -> PlayCommand:
    exp = time.monotonic() + 5 if expires_at is None else expires_at
    return PlayCommand(
        id="1",
        text="t",
        priority="NORMAL",
        category="engineer",
        event_id=event_id,
        ttl_ms=5000,
        expires_at=exp,
    )


def test_cooldown_blocks_duplicate_event():
    mod = PlaybackModerator(cooldown_s=2.0)
    now = time.monotonic()
    assert mod.should_play(_cmd("fuel_low"), now=now) is True
    mod.mark_played(_cmd("fuel_low"), now=now)
    assert mod.should_play(_cmd("fuel_low"), now=now + 0.5) is False


def test_expired_command_rejected():
    mod = PlaybackModerator()
    assert mod.should_play(_cmd("x", expires_at=time.monotonic() - 1)) is False


def test_different_event_ids_not_blocked():
    mod = PlaybackModerator(cooldown_s=2.0)
    now = time.monotonic()
    assert mod.should_play(_cmd("a"), now=now) is True
    mod.mark_played(_cmd("a"), now=now)
    assert mod.should_play(_cmd("b"), now=now + 0.1) is True
