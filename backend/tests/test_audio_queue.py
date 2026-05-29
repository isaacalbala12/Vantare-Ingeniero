"""Tests para AudioQueueManager."""

import asyncio
import time
import pytest

from src.services.audio_queue import AudioQueueManager
from src.models.messages import QueuedMessage, SoundType, MessagePriority


def test_immediate_before_regular():
    mgr = AudioQueueManager()
    reg = QueuedMessage(message_id="r1", text="reg", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM)
    imm = QueuedMessage(message_id="i1", text="imm", sound_type=SoundType.IMPORTANT, priority=MessagePriority.HIGH)
    mgr.enqueue(reg)
    mgr.enqueue(imm)
    assert mgr._dequeue_next().message_id == "i1"


def test_higher_priority_first():
    mgr = AudioQueueManager()
    low = QueuedMessage(message_id="l1", text="low", sound_type=SoundType.IMPORTANT, priority=MessagePriority.LOW)
    high = QueuedMessage(message_id="h1", text="high", sound_type=SoundType.IMPORTANT, priority=MessagePriority.CRITICAL)
    mgr.enqueue(low)
    mgr.enqueue(high)
    assert mgr._dequeue_next().message_id == "h1"


def test_expired_discarded():
    mgr = AudioQueueManager()
    msg = QueuedMessage(
        message_id="e1", text="exp", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM,
        ttl_seconds=0.1, created_at=time.time() - 1.0,
    )
    mgr.enqueue(msg)
    assert mgr._dequeue_next() is None


def test_keep_quiet_filters_regular():
    mgr = AudioQueueManager()
    mgr.set_keep_quiet(True)
    mgr.enqueue(QueuedMessage(message_id="r1", text="reg", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM))
    assert len(mgr._regular) == 0


def test_keep_quiet_allows_critical():
    mgr = AudioQueueManager()
    mgr.set_keep_quiet(True)
    mgr.enqueue(QueuedMessage(message_id="c1", text="crit", sound_type=SoundType.CRITICAL, priority=MessagePriority.CRITICAL))
    assert len(mgr._immediate) == 1


def test_verbosity_medium_filters_low():
    mgr = AudioQueueManager()
    mgr.set_verbosity(5)
    low = QueuedMessage(message_id="l1", text="low", sound_type=SoundType.REGULAR, priority=MessagePriority.LOW)
    med = QueuedMessage(message_id="m1", text="med", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM)
    mgr.enqueue(low)
    mgr.enqueue(med)
    assert len(mgr._regular) == 1
    assert mgr._regular[0][2].priority == MessagePriority.MEDIUM


def test_verbosity_low_filters_medium():
    mgr = AudioQueueManager()
    mgr.set_verbosity(10)
    mgr.enqueue(QueuedMessage(message_id="m1", text="med", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM))
    assert len(mgr._regular) == 0


def test_validator_called_with_latest_state():
    mgr = AudioQueueManager()
    mgr.update_state({"fuel_remaining": 5.0})
    calls = []
    mgr.register_validator("test_type", lambda msg, state: calls.append(state.get("fuel_remaining")))
    msg = QueuedMessage(
        message_id="v1", text="val", sound_type=SoundType.REGULAR,
        priority=MessagePriority.MEDIUM, event_type="test_type",
    )
    mgr.enqueue(msg)
    mgr._validate(mgr._dequeue_next())
    assert calls == [5.0]


def test_future_due_regular_not_blocked_by_immediate():
    mgr = AudioQueueManager()
    imm = QueuedMessage(
        message_id="i1", text="imm", sound_type=SoundType.IMPORTANT, priority=MessagePriority.CRITICAL,
        due_time=time.time() + 60,
    )
    reg = QueuedMessage(message_id="r1", text="reg", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM)
    mgr.enqueue(imm)
    mgr.enqueue(reg)
    popped = mgr._dequeue_next()
    assert popped is not None
    assert popped.message_id == "r1"


@pytest.mark.asyncio
async def test_start_stop():
    mgr = AudioQueueManager()
    task = asyncio.create_task(mgr.start())
    # Wake the loop by enqueuing, then stop
    mgr.enqueue(QueuedMessage(message_id="wake", text="wake", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM))
    await asyncio.sleep(0.01)
    await mgr.stop()
    await task
    assert mgr._running is False
