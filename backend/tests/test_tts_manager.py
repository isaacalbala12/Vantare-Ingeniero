from unittest.mock import AsyncMock, MagicMock

import pytest
from src.voice.spotter_cache import SpotterPhraseCache
from src.voice.tts_manager import TTSManager


@pytest.mark.asyncio
async def test_cache_hit_skips_edge():
    edge = MagicMock()
    edge.synthesize = AsyncMock(return_value=b"live")
    cache = SpotterPhraseCache(edge)
    cache._bytes["k"] = b"cached"
    mgr = TTSManager(edge=edge, spotter_cache=cache)
    out = await mgr.synthesize("text", cache_key="k")
    assert out == b"cached"
    edge.synthesize.assert_not_called()
