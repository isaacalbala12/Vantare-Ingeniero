from fastapi import APIRouter, Request
from src.config import settings
from src.app_runtime.runtime import native_telemetry_enabled
from src.services.lmu_api import get_cache_sizes
from src.services.asr_service import get_asr_status

router = APIRouter()

@router.get("/health")
async def health_check(request: Request):
    """Diagnóstico completo de los componentes del backend."""
    
    reader = getattr(request.app.state, "telemetry_reader", None)
    shm_status = "offline"
    last_lap = 0
    if reader:
        state = reader.get_state()
        if state is not None:
            shm_status = "connected"
            if state.player:
                last_lap = state.player.current_lap

    cache_info = get_cache_sizes()
    llm_api_configured = bool(settings.LLM_API_KEY)

    if native_telemetry_enabled() and shm_status == "connected":
        telemetry_source = "native"
    else:
        telemetry_source = "offline"

    return {
        "status": "ok",
        "telemetry": {
            "source": telemetry_source,
            "shared_memory_status": shm_status,
            "native_enabled": native_telemetry_enabled(),
        },
        "shared_memory": {
            "status": shm_status,
            "offline_mode": getattr(reader, "offline", True) if reader else True,
            "last_lap": last_lap
        },
        "frontend_telemetry": {
            "received": getattr(request.app.state, "latest_client_frame", None) is not None,
        },
        "lmu_api": {
            "status": "active" if cache_info.get("drivers", 0) > 0 or cache_info.get("brakes", 0) > 0 else "idle",
            "cache": cache_info
        },
        "llm": {
            "configured": llm_api_configured,
            "model": settings.LLM_MODEL
        },
        "asr": get_asr_status(),
    }
