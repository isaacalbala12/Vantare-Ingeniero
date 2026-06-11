import asyncio
import logging

import edge_tts

logger = logging.getLogger("vantare.edge_tts")


class EdgeTTSService:
    """Servicio de síntesis de voz usando Edge TTS (Microsoft, cloud).

    No requiere modelos locales. Genera audio MP3 vía la API de Azure Cognitive
    Services. Voz por defecto: es-ES-AlvaroNeural (castellano, masculino).
    """

    def __init__(self, voice: str = "es-ES-AlvaroNeural") -> None:
        self._voice = voice
        logger.info("EdgeTTSService initialized (voice=%s)", voice)

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        """Sintetiza texto a audio MP3 usando Edge TTS.

        Args:
            text: Texto a sintetizar.
            voice: Voz Edge opcional; si no se indica, usa la del servicio.

        Returns:
            bytes del audio en formato MP3.

        Raises:
            asyncio.TimeoutError: Si la síntesis excede 30 segundos.
            Exception: Si falla la conexión o cualquier error de red.
        """
        if not text or not text.strip():
            return b""

        selected_voice = voice.strip() if voice and voice.strip() else self._voice
        communicate = edge_tts.Communicate(text, selected_voice)

        async def _stream() -> bytes:
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
            return audio_bytes

        try:
            audio_bytes = await asyncio.wait_for(_stream(), timeout=30.0)
            logger.info(
                "Edge TTS: %d chars -> %d bytes MP3 (voice=%s)",
                len(text),
                len(audio_bytes),
                selected_voice,
            )
            return audio_bytes
        except TimeoutError:
            logger.error("Edge TTS timeout tras 30s (%d chars)", len(text))
            raise
