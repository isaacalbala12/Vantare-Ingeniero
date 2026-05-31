import logging

from elevenlabs.client import AsyncElevenLabs

logger = logging.getLogger("vantare.elevenlabs_tts")


class ElevenLabsTTSService:
    """Servicio de síntesis de voz usando ElevenLabs (cloud).

    Genera audio MP3 de alta calidad mediante la API de ElevenLabs.
    Voz por defecto: pNInz6obpgDQGcFmaJgB (Adam, español masculino).
    Modelo: eleven_flash_v2_5 (optimizado para baja latencia).
    """

    def __init__(self, api_key: str, voice_id: str = "pNInz6obpgDQGcFmaJgB") -> None:
        self._client = AsyncElevenLabs(api_key=api_key)
        self._voice_id = voice_id
        logger.info(
            "ElevenLabsTTSService initialized (voice_id=%s, model=eleven_flash_v2_5)",
            voice_id,
        )

    async def synthesize(self, text: str) -> bytes:
        """Sintetiza texto a audio MP3 usando ElevenLabs.

        Args:
            text: Texto a sintetizar.

        Returns:
            bytes del audio en formato MP3.

        Raises:
            Exception: Si falla la conexión, cuota insuficiente, o cualquier error.
        """
        if not text or not text.strip():
            return b""

        chunks: list[bytes] = []
        async for chunk in self._client.text_to_speech.convert(
            voice_id=self._voice_id,
            text=text,
            model_id="eleven_flash_v2_5",
            output_format="mp3_44100_128",
        ):
            chunks.append(chunk)

        audio_bytes = b"".join(chunks)

        logger.info(
            "ElevenLabs TTS: %d chars -> %d bytes MP3 (voice_id=%s)",
            len(text),
            len(audio_bytes),
            self._voice_id,
        )
        return audio_bytes
