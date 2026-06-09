import os
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict

# Determinar la ruta al .env según el modo de ejecución.
# PyInstaller --onedir: sys._MEIPASS = _internal/ (el .env se copia allí).
# Dev: el .env está en backend/ (un nivel arriba de src/config.py).
if getattr(sys, "_MEIPASS", None):
    ENV_FILE = os.path.join(sys._MEIPASS, ".env")
else:
    ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")


class Settings(BaseSettings):
    # LLM (motor de lenguaje genérico, compatible con OpenAI API)
    # Permite cambiar de proveedor fácilmente (CrofAI, Groq, vLLM, etc.)
    LLM_BASE_URL: str = "https://bright-climb-alan-reforms.trycloudflare.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "hipfire-qwen"

    # DEPRECATED: CrofAI (mantenido por compatibilidad)
    CROFAI_API_KEY: str = ""  # DEPRECATED - usar LLM_API_KEY
    CROFAI_BASE_URL: str = "https://crof.ai/v1"  # DEPRECATED - usar LLM_BASE_URL

    # Groq (legacy, usado por el endpoint /ask)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama3-8b-8192"

    # LMU API Settings
    LMU_REST_URL: str = "http://localhost:6397"
    POLL_INTERVAL_API: float = 3.0

    # Lector Settings
    TELEMETRY_POLL_RATE: float = 0.05  # 50ms (20Hz)
    STRATEGY_POLL_RATE: float = 2.0  # 2.0s (0.5Hz)

    # Server Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8008
    DEBUG: bool = False

    # Configuración de Pistas
    TRACK_LENGTH_DEFAULT: float = 7004.0  # Spa-Francorchamps por defecto (metros)

    # Spotter / Voz
    USE_SWEARY_MESSAGES: bool = False
    SPOTTER_PROXIMITY_THRESHOLD_M: float = 3.0
    SPOTTER_OFF_QUALIFYING: bool = True
    SPOTTER_EXCLUDE_STOPPED: bool = True
    AUDIO_DUCK_LEVEL: float = 0.2  # 20% volumen LMU durante TTS

    # MQTT (opt-in, broker local por defecto)
    MQTT_ENABLED: bool = False
    MQTT_BROKER: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_TOPIC: str = "vantare/telemetry"

    # TTS Settings
    TTS_BACKEND: str = "edge"  # "edge", "piper", o "elevenlabs"
    EDGE_TTS_VOICE: str = "es-ES-AlvaroNeural"
    TTS_MODEL_PATH: str = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "services", "tts_models", "es_ES-carlfm-x_low.onnx"
    )
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "pNInz6obpgDQGcFmaJgB"

    # Gemini TTS Settings
    GEMINI_API_KEY: str = ""
    GEMINI_TTS_VOICE: str = "Kore"

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")


settings = Settings()
