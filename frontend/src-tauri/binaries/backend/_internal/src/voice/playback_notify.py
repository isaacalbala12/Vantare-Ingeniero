from __future__ import annotations

from collections.abc import Callable

from src.models.messages import BaseMessage, VoicePlaybackEndMessage, VoicePlaybackStartMessage
from src.voice.play_command import PlayCommand

BroadcastFn = Callable[[BaseMessage], None]

_SPOTTER_CATEGORIES = frozenset(
    {
        "proximity",
        "pit_limiter",
        "fuel",
        "safety_car",
        "damage",
        "puncture",
        "impact",
        "limiter",
    }
)


def derive_playback_source(category: str) -> str:
    return "spotter" if category.lower() in _SPOTTER_CATEGORIES else "engineer"


class VoicePlaybackNotifier:
    """Emite eventos WS cuando el backend reproduce audio (overlay UI)."""

    def __init__(self, broadcast: BroadcastFn) -> None:
        self._broadcast = broadcast

    def notify_start(self, cmd: PlayCommand) -> str:
        self._broadcast(
            VoicePlaybackStartMessage(
                event="voice_playback_start",
                playback_id=cmd.id,
                text=cmd.text,
                category=cmd.category,
                priority=cmd.priority,
                source=derive_playback_source(cmd.category),
            )
        )
        return cmd.id

    def notify_end(self, playback_id: str) -> None:
        self._broadcast(
            VoicePlaybackEndMessage(
                event="voice_playback_end",
                playback_id=playback_id,
            )
        )
