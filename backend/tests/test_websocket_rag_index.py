"""Tests de indexación RAG async en websocket sidecar."""

import asyncio
import time

import pytest

from src.routers.websocket import _index_events_async


class _SlowEventStore:
    def __init__(self) -> None:
        self.calls = 0

    def store_events_batch(self, frames) -> None:
        self.calls += 1
        time.sleep(0.15)


@pytest.mark.asyncio
async def test_index_events_async_does_not_block_event_loop():
    """store_events_batch lento no debe congelar otras coroutines."""
    store = _SlowEventStore()
    frame = {"lap_number": 3, "session_type": "race"}
    events = [{"type": "lap_completed", "lap": 3}]

    tick_done = asyncio.Event()

    async def heartbeat():
        await asyncio.sleep(0.05)
        tick_done.set()

    heartbeat_task = asyncio.create_task(heartbeat())
    index_task = asyncio.create_task(_index_events_async(store, frame, events))

    await asyncio.wait_for(tick_done.wait(), timeout=0.12)
    await index_task

    assert store.calls == 1
    heartbeat_task.cancel()
