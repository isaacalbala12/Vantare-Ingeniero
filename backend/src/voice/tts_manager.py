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

    def _provider_for_role(self, tts_role: str) -> str:
        if tts_role == "spotter":
            return self._routing.provider_spotter
        return self._routing.provider_engineer

    def _should_use_spotter_cache(self, *, cache_key: str | None, tts_role: str, provider: str) -> bool:
        if not cache_key or not self._cache:
            return False
        if tts_role == "spotter" and provider == "gemini":
            return False
        return True

    async def synthesize(
        self,
        text: str,
        *,
        cache_key: str | None = None,
        tts_role: str = "engineer",
    ) -> bytes:
        provider = self._provider_for_role(tts_role)
        if self._should_use_spotter_cache(cache_key=cache_key, tts_role=tts_role, provider=provider):
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug("TTS cache hit key=%s", cache_key)
                return cached

        if provider == "gemini" and self._gemini is not None:
            try:
                voice = (
                    self._routing.gemini_voice_spotter
                    if tts_role == "spotter"
                    else self._routing.gemini_voice_engineer
                )
                return await self._gemini.synthesize(text, voice=voice)
            except Exception as exc:
                logger.warning("Gemini TTS failed, fallback Edge: %s", exc)

        if self._edge is None:
            raise RuntimeError("Edge TTS unavailable")

        edge_voice = (
            self._routing.edge_voice_spotter if tts_role == "spotter" else self._routing.edge_voice_engineer
        )
        audio = await self._edge.synthesize(text, voice=edge_voice)
        if not audio:
            raise RuntimeError("Empty TTS response")
        return audio
