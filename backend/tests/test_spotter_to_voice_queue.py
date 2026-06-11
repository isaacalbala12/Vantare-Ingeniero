"""E2E: SpotterService -> VoiceBridge.send -> PlayCommand in VoiceQueue (IMMEDIATE)."""

import asyncio
from unittest.mock import MagicMock

import pytest
from src.intelligence.spotter import SpotterService
from src.intelligence.spotter_adapter import frame_to_spotter_tick
from src.voice.bridge import VoiceBridge
from src.voice.voice_queue import VoiceQueue
from tests.fixtures.spotter.helpers import load_frame


@pytest.mark.asyncio
async def test_spotter_proximity_enqueues_immediate_play_command():
    q = VoiceQueue()
    ws_cb = MagicMock()
    bridge = VoiceBridge(ws_broadcast=ws_cb, voice_queue=q, enabled=True)
    spotter = SpotterService(broadcast_callback=bridge.send, proximity_threshold_m=3.0, enabled=True)
    frame = load_frame("world_overlap_no_path_delta")
    tick = frame_to_spotter_tick(frame, advice=None)
    spotter.evaluate_tick(tick)
    await asyncio.sleep(0.05)
    assert q.qsize() >= 1, "Spotter debe encolar al menos un PlayCommand en VoiceQueue"
    cmd = await q.get()
    assert cmd.priority == "IMMEDIATE", f"Proximidad spotter debe ser IMMEDIATE, got {cmd.priority}"
    assert "proximity" in cmd.category or cmd.event_id == "proximity", (
        f"El comando debe ser proximidad, got category={cmd.category} event_id={cmd.event_id}"
    )
