"""REST endpoint for user-facing configuration — get/save settings from the frontend."""

import logging
from fastapi import APIRouter, Request

from src.config import settings

logger = logging.getLogger("vantare.config_router")

router = APIRouter()


@router.get("/config")
async def get_config():
    """Return current user-facing settings (frontend-readable format)."""
    return {
        "chiefVoice": settings.EDGE_TTS_VOICE,
        "spotterVoice": settings.SPOTTER_TTS_VOICE,
        "chiefRate": settings.CHIEF_TTS_RATE,
        "spotterRate": settings.SPOTTER_TTS_RATE,
        "chiefPitch": settings.CHIEF_TTS_PITCH,
        "spotterPitch": settings.SPOTTER_TTS_PITCH,
        "spotterVolumeBoost": settings.SPOTTER_VOLUME_BOOST,
        "audioOutputDevice": settings.AUDIO_OUTPUT_DEVICE,
        "interruptThreshold": settings.INTERRUPT_THRESHOLD,
        "autoVerbosityEnabled": settings.AUTO_VERBOSITY_ENABLED,
        "spotterGapForClear": settings.SPOTTER_GAP_FOR_CLEAR,
        "spotterOverlapDelay": settings.SPOTTER_OVERLAP_DELAY,
        "spotterClearDelay": settings.SPOTTER_CLEAR_DELAY,
        "spotterRepeatFrequency": settings.SPOTTER_REPEAT_FREQUENCY,
        "spotterMinSpeed": settings.SPOTTER_MIN_SPEED,
        "spotterMaxClosingSpeed": settings.SPOTTER_MAX_CLOSING_SPEED,
        "spotterEnable3Wide": settings.SPOTTER_ENABLE_3WIDE,
        "fcyStopSpotter": settings.FCY_STOP_SPOTTER,
        "driverName": settings.DRIVER_NAME,
        "workerUrl": settings.WORKER_URL,
        "enableTemplates": settings.ENABLE_TEMPLATES,
    }


@router.put("/config")
async def save_config(request: Request):
    """Accept user-facing settings from the frontend and persist to JSON file."""
    try:
        payload = await request.json()
    except Exception as e:
        logger.error("Invalid JSON in config PUT: %s", e)
        return {"error": "Invalid JSON"}

    result = settings.save_user_config(payload)
    logger.info("User config saved: %s", result)
    return result
