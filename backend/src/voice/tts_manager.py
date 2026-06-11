from __future__ import annotations

import logging

from src.voice.tts_routing import TtsRouting

logger = logging.getLogger("vantare.tts_manager")


class TTSManager:
    """Edge TTS + Gemini + lookup en SpotterPhraseCache por rol."""

    def __init__(self, edge, gemini=None, spotter_cache=None, routing=None) -> None:
        self._edge = edge
        self._gemini = gemini
        self._cache = spotter_cache
        self._routing = routing or TtsRouting()

    async def synthesize(
        self,
        text: str,
        *,
        cache_key: str | None = None,
        tts_role: str = "engineer",
    ) -> bytes:
        if cache_key and self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug("TTS cache hit key=%s", cache_key)
                return cached
        provider = (
            self._routing.provider_spotter if tts_role == "spotter" else self._routing.provider_engineer
        )
        if provider == "gemini" and self._gemini is not None:
            try:
                return await self._gemini.synthesize(text)
            except Exception as exc:
                logger.warning("Gemini TTS failed, fallback Edge: %s", exc)
        if self._edge is None:
            raise RuntimeError("Edge TTS unavailable")
        audio = await self._edge.synthesize(text)
        if not audio:
            raise RuntimeError("Empty TTS response")
        return audio
