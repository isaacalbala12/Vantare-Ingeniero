import asyncio
import time
from unittest.mock import MagicMock

import pytest
from src.voice.moderator import PlaybackModerator
from src.voice.play_command import PlayCommand
from src.voice.playback_notify import VoicePlaybackNotifier
from src.voice.player_pygame import MockAudioPlayer
from src.voice.service import voice_loop
from src.voice.voice_queue import VoiceQueue


@pytest.mark.asyncio
async def test_voice_loop_plays_non_expired_command():
    q = VoiceQueue()
    player = MockAudioPlayer()
    mod = PlaybackModerator(cooldown_s=0.0)
    cmd = PlayCommand(
        id="1",
        text="test",
        priority="IMMEDIATE",
        category="spotter",
        event_id="t",
        ttl_ms=5000,
        expires_at=time.monotonic() + 5,
    )
    await q.put(cmd)
    task = asyncio.create_task(voice_loop(q, player, mod, tts=None))
    await asyncio.sleep(0.08)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert player.played == ["test"]


@pytest.mark.asyncio
async def test_voice_loop_skips_expired_command():
    q = VoiceQueue()
    player = MockAudioPlayer()
    mod = PlaybackModerator(cooldown_s=0.0)
    cmd = PlayCommand(
        id="1",
        text="late",
        priority="IMMEDIATE",
        category="spotter",
        event_id="late",
        ttl_ms=100,
        expires_at=time.monotonic() - 1,
    )
    await q.put(cmd)
    task = asyncio.create_task(voice_loop(q, player, mod, tts=None))
    await asyncio.sleep(0.08)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert player.played == []


@pytest.mark.asyncio
async def test_voice_loop_notifies_playback_lifecycle():
    q = VoiceQueue()
    player = MockAudioPlayer()
    mod = PlaybackModerator(cooldown_s=0.0)
    broadcast = MagicMock()
    notifier = VoicePlaybackNotifier(broadcast)
    cmd = PlayCommand(
        id="pb-1",
        text="Combustible bajo",
        priority="IMMEDIATE",
        category="fuel",
        event_id="fuel_low",
        ttl_ms=5000,
        expires_at=time.monotonic() + 5,
    )
    await q.put(cmd)
    task = asyncio.create_task(
        voice_loop(q, player, mod, tts=None, playback_notify=notifier)
    )
    await asyncio.sleep(0.08)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert broadcast.call_count == 2
    start_msg = broadcast.call_args_list[0].args[0]
    end_msg = broadcast.call_args_list[1].args[0]
    assert start_msg.event == "voice_playback_start"
    assert end_msg.event == "voice_playback_end"
    assert start_msg.playback_id == end_msg.playback_id == "pb-1"
