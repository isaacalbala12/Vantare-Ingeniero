from __future__ import annotations

import time

from src.voice.play_command import PlayCommand


class PlaybackModerator:
    def __init__(self, cooldown_s: float = 1.5) -> None:
        self._cooldown_s = cooldown_s
        self._last_played: dict[str, float] = {}

    def should_play(self, cmd: PlayCommand, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if cmd.is_expired(now):
            return False
        last = self._last_played.get(cmd.event_id)
        if last is not None and (now - last) < self._cooldown_s:
            return False
        return True

    def mark_played(self, cmd: PlayCommand, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self._last_played[cmd.event_id] = now
