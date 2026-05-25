from fastapi import APIRouter, Request
from src.config import settings
from src.services.lmu_api import get_cache_sizes

router = APIRouter()

@router.get("/health")
async def health_check(request: Request):
    """Diagnóstico completo de los componentes del backend."""
    
    # 1. Verificar estado de la Shared Memory de LMU
    reader = getattr(request.app.state, "telemetry_reader", None)
    shm_status = "offline"
    last_lap = 0
    if reader:
        state = reader.get_state()
        if state is not None:
            shm_status = "connected"
            if state.player:
                last_lap = state.player.current_lap

    # 2. Verificar estado de la API REST de LMU
    cache_info = get_cache_sizes()

    # 3. Verificar estado del LLM
    llm_api_configured = bool(settings.LLM_API_KEY)

    return {
        "status": "ok",
        "shared_memory": {
            "status": shm_status,
            "offline_mode": getattr(reader, "offline", True) if reader else True,
            "last_lap": last_lap
        },
        "lmu_api": {
            "status": "active" if cache_info.get("drivers", 0) > 0 or cache_info.get("brakes", 0) > 0 else "idle",
            "cache": cache_info
        },
        "llm": {
            "configured": llm_api_configured,
            "model": settings.LLM_MODEL
        }
    }
