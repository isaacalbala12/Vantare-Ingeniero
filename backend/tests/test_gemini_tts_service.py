"""Tests de GeminiTTSService (async offload + contrato vacío)."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from src.services.gemini_tts_service import GeminiTTSService


@pytest.mark.asyncio
async def test_synthesize_empty_text_returns_empty_bytes():
    svc = GeminiTTSService(api_key="test-key")
    result = await svc.synthesize("   ")
    assert result == b""


@pytest.mark.asyncio
async def test_synthesize_does_not_block_event_loop():
    svc = GeminiTTSService(api_key="test-key")

    def slow_sync(text: str, voice_name: str = "Kore") -> bytes:
        time.sleep(0.12)
        return b"RIFF...."

    tick_done = asyncio.Event()

    async def heartbeat():
        await asyncio.sleep(0.05)
        tick_done.set()

    with patch.object(GeminiTTSService, "_synthesize_sync", side_effect=slow_sync):
        heartbeat_task = asyncio.create_task(heartbeat())
        synth_task = asyncio.create_task(svc.synthesize("Hola piloto"))

        await asyncio.wait_for(tick_done.wait(), timeout=0.1)
        result = await synth_task

    assert result == b"RIFF...."
    heartbeat_task.cancel()
