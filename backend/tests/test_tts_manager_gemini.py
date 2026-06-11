import pytest
from unittest.mock import AsyncMock, MagicMock
from src.voice.tts_manager import TTSManager
from src.voice.tts_routing import TtsRouting


@pytest.mark.asyncio
async def test_synthesize_uses_gemini_when_routing_says_so():
    edge = MagicMock()
    edge.synthesize = AsyncMock(return_value=b"edge")
    gemini = MagicMock()
    gemini.synthesize = AsyncMock(return_value=b"RIFF")
    routing = TtsRouting(provider_engineer="gemini", provider_spotter="edge")

    mgr = TTSManager(edge=edge, gemini=gemini, spotter_cache=None, routing=routing)
    out = await mgr.synthesize("Hola boxes", tts_role="engineer")
    assert out == b"RIFF"
    gemini.synthesize.assert_awaited_once()
    edge.synthesize.assert_not_awaited()


@pytest.mark.asyncio
async def test_gemini_unavailable_falls_back_to_edge():
    edge = MagicMock()
    edge.synthesize = AsyncMock(return_value=b"edge-bytes")
    routing = TtsRouting(provider_engineer="gemini")
    mgr = TTSManager(edge=edge, gemini=None, spotter_cache=None, routing=routing)
    out = await mgr.synthesize("test", tts_role="engineer")
    assert out == b"edge-bytes"
