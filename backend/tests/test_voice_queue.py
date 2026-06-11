import time

import pytest
from src.voice.play_command import PlayCommand
from src.voice.voice_queue import VoiceQueue


def _cmd(priority: str, event_id: str, *, expires_in: float = 5.0) -> PlayCommand:
    return PlayCommand(
        id=event_id,
        text=event_id,
        priority=priority,  # type: ignore[arg-type]
        category="spotter" if priority == "IMMEDIATE" else "engineer",
        event_id=event_id,
        ttl_ms=int(expires_in * 1000),
        expires_at=time.monotonic() + expires_in,
    )


@pytest.mark.asyncio
async def test_immediate_dequeued_before_normal():
    q = VoiceQueue(maxsize=16)
    await q.put(_cmd("NORMAL", "a"))
    await q.put(_cmd("IMMEDIATE", "b"))
    first = await q.get()
    assert first.event_id == "b"


@pytest.mark.asyncio
async def test_fifo_within_same_priority():
    q = VoiceQueue(maxsize=16)
    await q.put(_cmd("NORMAL", "first"))
    await q.put(_cmd("NORMAL", "second"))
    assert (await q.get()).event_id == "first"
    assert (await q.get()).event_id == "second"


@pytest.mark.asyncio
async def test_full_queue_drops_oldest():
    q = VoiceQueue(maxsize=2)
    await q.put(_cmd("NORMAL", "old"))
    await q.put(_cmd("NORMAL", "mid"))
    await q.put(_cmd("IMMEDIATE", "new"))
    assert (await q.get()).event_id == "new"
    assert q.qsize() == 1
