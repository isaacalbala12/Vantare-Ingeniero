import logging
import wave
import io

from google.genai import types
from google.genai.types import SpeechConfig, PrebuiltVoiceConfig

logger = logging.getLogger("vantare.gemini_tts")


class GeminiTTSService:
    """Servicio de síntesis de voz usando Gemini 3.1 Flash TTS (Google AI Studio, cloud).

    Genera audio WAV PCM vía la API de Google AI Studio.
    Voz por defecto: Kore (masculina, firme).
    """

    def __init__(self, api_key: str, voice_name: str = "Kore") -> None:
        """Inicializa el servicio.

        Args:
            api_key: API key de Google AI Studio.
            voice_name: Nombre de la voz (ej. "Kore").
        """
        self.api_key = api_key
        self.voice_name = voice_name
        self._client = None

    def _get_client(self):
        """Obtiene o crea el cliente de Google GenAI."""
        if self._client is None:
            self._client = google.genai.Client(api_key=self.api_key)
        return self._client

    async def synthesize(self, text: str) -> bytes:
        """Sintetiza texto a audio WAV.

        Args:
            text: Texto a sintetizar (máx 2000 caracteres).

        Returns:
            Bytes del audio WAV (24000 Hz, mono, 16-bit PCM).
        """
        if not text or not text.strip():
            raise ValueError("Texto vacío")

        if len(text) > 2000:
            logger.warning("Texto Gemini truncado de %d a 2000 caracteres", len(text))
            text = text[:1997] + "..."

        client = self._get_client()

        # Configurar respuesta con modalidad de audio
        response_modalities = ["AUDIO"]

        # Configurar voz
        voice_config = types.VoiceConfig(prebuilt_voice=types.PrebuiltVoiceConfig(voice_name=self.voice_name))

        # Solicitar generación de audio
        response = client.models.generate_content(
            model="gemini-3.1-flash-tts-preview",
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=response_modalities,
                speech_config=types.SpeechConfig(voice_config=voice_config),
            ),
        )

        # Extraer datos PCM del response
        if not response.candidates or not response.candidates[0].content.parts:
            raise ValueError("Respuesta vacía o sin audio")

        inline_data = response.candidates[0].content.parts[0].inline_data
        if not inline_data or inline_data.mime_type != "audio/pcm":
            raise ValueError(f"Formato de audio no soportado: {inline_data.mime_type if inline_data else 'N/A'}")

        pcm_data = inline_data.data

        # Convertir PCM a WAV (24000 Hz, mono, 16-bit)
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(24000)  # 24 kHz
            wav_file.writeframes(pcm_data)

        return wav_buffer.getvalue()
