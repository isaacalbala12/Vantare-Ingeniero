"""Application settings loaded from environment variables + persisted user config."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import json
import os


class Settings(BaseSettings):
    """Application settings loaded from .env file or environment variables."""

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8008
    DEBUG: bool = False

    # Frontend origin for CORS
    FRONTEND_ORIGIN: str = "http://localhost:1420"

    # LLM Configuration
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = "hipfire-qwen"
    LLM_API_KEY: str = ""

    # Worker proxy URL (Cloudflare Worker for license key validation + LLM proxy)
    WORKER_URL: str = "https://vantare-llm-proxy.workers.dev"

    # LMU REST API
    LMU_REST_URL: str = ""
    POLL_INTERVAL_API: float = 3.0

    # Telemetry and Strategy polling rates
    TELEMETRY_POLL_RATE: float = 0.05
    STRATEGY_POLL_RATE: float = 2.0

    # TTS Configuration
    TTS_BACKEND: str = "edge"
    TTS_MODEL_PATH: str = ""

    # Edge TTS — chief voice (jefe de equipo)
    EDGE_TTS_VOICE: str = "es-ES-AlvaroNeural"

    # Edge TTS — spotter voice
    SPOTTER_TTS_VOICE: str = "es-MX-JorgeNeural"

    # TTS rate/pitch adjustments
    CHIEF_TTS_RATE: int = 0
    SPOTTER_TTS_RATE: int = 5
    CHIEF_TTS_PITCH: int = 0
    SPOTTER_TTS_PITCH: int = 5

    # Volume
    SPOTTER_VOLUME_BOOST: int = 20

    # Audio output device (empty = default)
    AUDIO_OUTPUT_DEVICE: str = ""

    # Interrupt threshold: NEVER | SPOTTER | CRITICAL | IMPORTANT
    INTERRUPT_THRESHOLD: str = "SPOTTER"

    # Auto verbosity
    AUTO_VERBOSITY_ENABLED: bool = True

    # Spotter params
    SPOTTER_GAP_FOR_CLEAR: float = 5.0
    SPOTTER_OVERLAP_DELAY: int = 300
    SPOTTER_CLEAR_DELAY: int = 500
    SPOTTER_REPEAT_FREQUENCY: float = 3.0
    SPOTTER_MIN_SPEED: float = 5.0
    SPOTTER_MAX_CLOSING_SPEED: float = 30.0
    SPOTTER_ENABLE_3WIDE: bool = True
    FCY_STOP_SPOTTER: bool = True

    # Driver name for {driver_name} templates
    DRIVER_NAME: str = ""

    # Template substitution
    ENABLE_TEMPLATES: bool = True

    # ElevenLabs TTS (optional)
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_VOICE_ID: str = ""

    # Gemini TTS (optional)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_TTS_VOICE: str = "Aoede"

    # Path to persisted user config JSON (overrides env defaults at runtime)
    _config_path: str = ""

    def model_post_init(self, __context):
        """After init, try loading persisted config from JSON file."""
        self._config_path = os.environ.get(
            "VANTARE_CONFIG_PATH",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "user_config.json")
        )
        self._load_user_config()

    def _load_user_config(self):
        """Load persisted user config from JSON and overlay onto env-based defaults."""
        if not self._config_path:
            return
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, "r") as f:
                    data = json.load(f)
                # Map frontend-style keys to backend env-style keys
                mapping = {
                    "chiefVoice": "EDGE_TTS_VOICE",
                    "spotterVoice": "SPOTTER_TTS_VOICE",
                    "chiefRate": "CHIEF_TTS_RATE",
                    "spotterRate": "SPOTTER_TTS_RATE",
                    "chiefPitch": "CHIEF_TTS_PITCH",
                    "spotterPitch": "SPOTTER_TTS_PITCH",
                    "spotterVolumeBoost": "SPOTTER_VOLUME_BOOST",
                    "audioOutputDevice": "AUDIO_OUTPUT_DEVICE",
                    "interruptThreshold": "INTERRUPT_THRESHOLD",
                    "autoVerbosityEnabled": "AUTO_VERBOSITY_ENABLED",
                    "spotterGapForClear": "SPOTTER_GAP_FOR_CLEAR",
                    "spotterOverlapDelay": "SPOTTER_OVERLAP_DELAY",
                    "spotterClearDelay": "SPOTTER_CLEAR_DELAY",
                    "spotterRepeatFrequency": "SPOTTER_REPEAT_FREQUENCY",
                    "spotterMinSpeed": "SPOTTER_MIN_SPEED",
                    "spotterMaxClosingSpeed": "SPOTTER_MAX_CLOSING_SPEED",
                    "spotterEnable3Wide": "SPOTTER_ENABLE_3WIDE",
                    "driverName": "DRIVER_NAME",
                    "workerUrl": "WORKER_URL",
                    "enableTemplates": "ENABLE_TEMPLATES",
                }
                for frontend_key, backend_attr in mapping.items():
                    if frontend_key in data:
                        setattr(self, backend_attr, data[frontend_key])
        except (json.JSONDecodeError, OSError) as e:
            import logging
            logging.getLogger("vantare.settings").warning(
                "Failed to load user config from %s: %s", self._config_path, e
            )

    def save_user_config(self, config_data: dict) -> dict:
        """Persist user-facing settings to JSON file and update this instance."""
        if not self._config_path:
            return {"error": "No config path configured"}
        try:
            # Load existing
            existing = {}
            if os.path.exists(self._config_path):
                with open(self._config_path, "r") as f:
                    existing = json.load(f)
            existing.update(config_data)
            # Write
            with open(self._config_path, "w") as f:
                json.dump(existing, f, indent=2)
            # Re-apply to this instance
            self._load_user_config()
            return {"status": "ok", "path": self._config_path}
        except (OSError, json.JSONDecodeError) as e:
            import logging
            logging.getLogger("vantare.settings").error(
                "Failed to save user config: %s", e
            )
            return {"error": str(e)}

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Singleton instance
settings = Settings()
