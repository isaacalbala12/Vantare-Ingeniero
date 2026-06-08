import os
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determinar la ruta al .env según el modo de ejecución.
# PyInstaller --onedir: sys._MEIPASS = _internal/ (el .env se copia allí).
# Dev: el .env está en backend/ (un nivel arriba de src/config.py).
if getattr(sys, '_MEIPASS', None):
    ENV_FILE = os.path.join(sys._MEIPASS, ".env")
else:
    ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")


class Settings(BaseSettings):
    # LLM (motor de lenguaje genérico, compatible con OpenAI API)
    # Permite cambiar de proveedor fácilmente (CrofAI, Groq, vLLM, etc.)
    LLM_BASE_URL: str = "https://api.stepfun.ai/step_plan/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "step-3.5-flash"

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
    STRATEGY_POLL_RATE: float = 2.0    # 2.0s (0.5Hz)

    # Windows native telemetry (Task 49 — no sidecar)
    NATIVE_TELEMETRY: bool = True
    SIDECAR_FALLBACK: bool = False

    # Server Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8008
    DEBUG: bool = False

    # Configuración de Pistas
    TRACK_LENGTH_DEFAULT: float = 7004.0  # Spa-Francorchamps por defecto (metros)

    # Spotter / Voz
    USE_SWEARY_MESSAGES: bool = False
    SPOTTER_PROXIMITY_THRESHOLD_M: float = 3.0
    SPOTTER_INVERT_LATERAL: bool = True  # LMU: eje X invertido respecto a convención sim-test
    SPOTTER_OFF_QUALIFYING: bool = True
    SPOTTER_EXCLUDE_STOPPED: bool = True
    SPOTTER_CLEAR_DELAY_S: float = 0.15
    SPOTTER_OVERLAP_DELAY_S: float = 2.0  # legacy UI; still-there usa HOLD_REPEAT
    SPOTTER_HOLD_REPEAT_S: float = 3.0
    SPOTTER_GAP_FREQUENCY_S: float = 30.0
    SPOTTER_CAR_LENGTH_M: float = 4.5
    SPOTTER_CLOSING_SPEED_MS: float = 12.0  # m/s relativo para "viene rápido"
    SPOTTER_MIN_SPEED_MS: float = 5.0
    SPOTTER_RACE_START_DELAY_S: float = 3.0
    SPOTTER_USE_3WIDE_LEFT_RIGHT: bool = True
    SPOTTER_FCY_PAUSE_MIN_S: float = 1.0
    SPOTTER_FCY_PAUSE_MAX_S: float = 3.0
    SPOTTER_CLEAR_TTL_MS: int = 2000
    PIT_MENU_DRY_RUN: bool = True
    PIT_MENU_CONFIRM_WRITES: bool = True
    LMU_SESSION_SETTINGS_POLL_S: float = 5.0
    ENABLE_COMMENTARY_BATCH: bool = False
    PIT_LIMITER_GRACE_S: float = 3.0  # LMU: in_pits antes de mSpeedLimiterActive
    PIT_LIMITER_EXIT_CHECK_S: float = 2.0  # CC: disengage_limiter tras salir de boxes
    PIT_LIMITER_MIN_SPEED_MS: float = 1.0  # CC: CarSpeed > 1 al entrar sin limiter
    PIT_LIMITER_ENTRY_WINDOW_S: float = 8.0  # Solo avisar al entrar en pit lane, no en garage
    PIT_LIMITER_DISENGAGE_WINDOW_S: float = 6.0  # Reintentos tras salida si LMU parpadea
    PIT_LIMITER_COOLDOWN_S: float = 30.0
    TTS_VOLUME_BOOST: float = 1.0  # multiplicador 0.5–2.0
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

    # ASR / Whisper (PTT local)
    WHISPER_PRELOAD: str = "startup"  # startup | first_question (onboarding futuro)
    WHISPER_MODEL: str = "small"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
