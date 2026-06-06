"""Tests para TraceStore."""

import asyncio
import os
import tempfile

import pytest

from src.persistence.trace_store import TraceStore


@pytest.fixture
def trace_dir(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setattr("src.persistence.trace_store.TRACES_DIR", tmp)
    yield tmp


class TestTraceStore:
    def test_record_and_list(self, trace_dir):
        store = TraceStore()
        tid = store.start_recording("test-trace")
        store.append_frame({"lap_number": 1, "speed": 50.0})
        store.append_frame({"lap_number": 1, "speed": 55.0})
        stopped = store.stop_recording()

        assert tid == "test-trace"
        assert stopped == "test-trace"
        traces = store.list_traces()
        assert len(traces) == 1
        assert traces[0]["id"] == "test-trace"
        assert traces[0]["frames"] == 2

    def test_cannot_start_twice(self, trace_dir):
        store = TraceStore()
        store.start_recording()
        with pytest.raises(RuntimeError):
            store.start_recording()

    @pytest.mark.asyncio
    async def test_playback_replays_frames(self, trace_dir):
        store = TraceStore()
        store.start_recording("pb")
        frames = [{"lap_number": i, "speed": float(i)} for i in range(3)]
        for f in frames:
            store.append_frame(f)
        store.stop_recording()

        received: list[dict] = []

        async def cb(frame):
            received.append(frame)

        count = await store.playback("pb", cb, speed=10.0)
        assert count == 3
        assert [f["lap_number"] for f in received] == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_playback_missing_trace(self, trace_dir):
        store = TraceStore()
        with pytest.raises(FileNotFoundError):
            await store.playback("nope", lambda f: None)
