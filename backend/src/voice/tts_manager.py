from __future__ import annotations

import logging

from src.voice.spotter_cache import SpotterPhraseCache

logger = logging.getLogger("vantare.tts_manager")


class TTSManager:
    """Edge TTS + lookup en SpotterPhraseCache."""

    def __init__(self, edge_service, spotter_cache: SpotterPhraseCache | None) -> None:
        self._edge = edge_service
        self._cache = spotter_cache

    async def synthesize(self, text: str, *, cache_key: str | None = None) -> bytes:
        if cache_key and self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug("TTS cache hit key=%s", cache_key)
                return cached
        if self._edge is None:
            raise RuntimeError("Edge TTS unavailable")
        audio = await self._edge.synthesize(text)
        if not audio:
            raise RuntimeError("Empty TTS response")
        return audio
