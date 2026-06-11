import time

import pytest
from src.voice.play_command import PlayCommand
from src.voice.voice_queue import VoiceQueue


def _cmd(priority: str, event_id: str, seq_hint: int = 0) -> PlayCommand:
    base = time.monotonic() + 5 + seq_hint * 0.001
    return PlayCommand(
        id=event_id,
        text=event_id,
        priority=priority,  # type: ignore[arg-type]
        category="spotter" if priority == "IMMEDIATE" else "engineer",
        event_id=event_id,
        ttl_ms=5000,
        expires_at=base,
    )


@pytest.mark.asyncio
async def test_full_queue_drops_normal_not_immediate():
    q = VoiceQueue(maxsize=2)
    await q.put(_cmd("IMMEDIATE", "spot1"))
    await q.put(_cmd("IMMEDIATE", "spot2"))
    await q.put(_cmd("NORMAL", "engineer1"))
    first = await q.get()
    assert first.event_id in ("spot1", "spot2")
    assert first.priority == "IMMEDIATE"
    remaining = []
    while q.qsize():
        remaining.append((await q.get()).event_id)
    assert "engineer1" in remaining
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_full_queue_drops_oldest_among_same_priority():
    q = VoiceQueue(maxsize=2)
    await q.put(_cmd("NORMAL", "old"))
    await q.put(_cmd("NORMAL", "mid"))
    await q.put(_cmd("IMMEDIATE", "new"))
    assert (await q.get()).event_id == "new"
    assert (await q.get()).event_id == "mid"
    assert q.qsize() == 0
