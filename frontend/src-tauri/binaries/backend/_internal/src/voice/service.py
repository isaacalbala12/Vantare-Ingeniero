from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.voice.moderator import PlaybackModerator
from src.voice.playback_notify import VoicePlaybackNotifier
from src.voice.voice_queue import VoiceQueue

logger = logging.getLogger("vantare.voice_loop")


async def voice_loop(
    queue: VoiceQueue,
    player: Any,
    moderator: PlaybackModerator,
    tts: object | None,
    ducking: Any | None = None,
    *,
    playback_notify: VoicePlaybackNotifier | None = None,
) -> None:
    while True:
        try:
            cmd = await queue.get()
            if not moderator.should_play(cmd):
                continue
            playback_id: str | None = None
            try:
                if playback_notify is not None:
                    playback_id = playback_notify.notify_start(cmd)
                if ducking:
                    ducking.duck_on()
                try:
                    if tts is not None and hasattr(tts, "synthesize"):
                        audio = await tts.synthesize(cmd.text, cache_key=cmd.wav_cache_key)
                        if hasattr(player, "play_bytes"):
                            await player.play_bytes(audio, priority=cmd.priority)
                        else:
                            await player.play_text(cmd.text, priority=cmd.priority)
                    else:
                        await player.play_text(cmd.text, priority=cmd.priority)
                    moderator.mark_played(cmd)
                finally:
                    if ducking:
                        ducking.duck_off()
            finally:
                if playback_notify is not None and playback_id is not None:
                    playback_notify.notify_end(playback_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("voice_loop error: %s", exc, exc_info=True)
