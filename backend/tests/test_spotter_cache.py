from unittest.mock import AsyncMock, MagicMock

import pytest
from src.voice.spotter_cache import SpotterPhraseCache, default_spotter_phrases


def test_default_phrases_non_empty():
    phrases = default_spotter_phrases()
    assert len(phrases) >= 10
    assert any("izquierda" in v.lower() for v in phrases.values())


@pytest.mark.asyncio
async def test_cache_stores_bytes_by_key():
    tts = MagicMock()
    tts.synthesize = AsyncMock(return_value=b"mp3bytes")
    cache = SpotterPhraseCache(tts)
    phrases = {"proximity_left": "Coche a la izquierda"}
    await cache.warm(phrases)
    assert cache.get("proximity_left") == b"mp3bytes"
    tts.synthesize.assert_awaited_once()


@pytest.mark.asyncio
async def test_warm_skips_empty_text():
    tts = MagicMock()
    tts.synthesize = AsyncMock(return_value=b"x")
    cache = SpotterPhraseCache(tts)
    await cache.warm({"bad": ""})
    assert cache.get("bad") is None
