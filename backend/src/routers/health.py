import time

from fastapi import APIRouter, Request
from src.app_runtime.runtime import native_telemetry_enabled
from src.config import settings
from src.services.asr_service import get_asr_status
from src.services.lmu_api import get_cache_sizes

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """Diagnóstico completo de los componentes del backend."""

    # 1. Verificar estado de la Shared Memory de LMU
    reader = getattr(request.app.state, "telemetry_reader", None)
    shm_status = "offline"
    last_lap = 0
    reader_offline = getattr(reader, "offline", True) if reader else True
    if reader:
        state = reader.get_state()
        if state is not None:
            if reader_offline:
                shm_status = "simulated"
            else:
                shm_status = "connected"
            if state.player:
                last_lap = state.player.current_lap

    if native_telemetry_enabled() and not reader_offline and shm_status == "connected":
        telemetry_source = "native"
    elif getattr(request.app.state, "latest_client_frame", None) is not None:
        telemetry_source = "frontend"
    else:
        telemetry_source = "offline" if reader_offline else "native"

    # 2. Verificar estado de la API REST de LMU
    cache_info = get_cache_sizes()

    # 3. Verificar estado del LLM
    llm_api_configured = bool(settings.LLM_API_KEY)

    spotter = getattr(request.app.state, "spotter_service", None)
    spotter_info: dict = {"enabled": None, "competitors": 0}
    strategy_service = getattr(request.app.state, "strategy_service", None)
    if strategy_service and hasattr(strategy_service, "snapshot_frame"):
        try:
            frame = strategy_service.snapshot_frame()
            if frame:
                spotter_info["competitors"] = len(frame.get("competitors") or [])
        except Exception:
            pass
    if spotter is not None:
        spotter_info["enabled"] = bool(getattr(spotter, "enabled", False))

    # 4. Race loop metrics
    hub = getattr(request.app.state, "telemetry_hub", None)
    race_loop = {
        "tick_count": getattr(hub, "tick_count", 0) if hub else 0,
        "last_tick_age_s": (
            round(time.monotonic() - hub.last_tick_monotonic, 3) if hub and hub.last_tick_monotonic > 0 else None
        ),
    }

    # 5. Voice metrics
    vq = getattr(request.app.state, "voice_queue", None)
    player = getattr(request.app.state, "voice_player", None)
    voice = {
        "backend_playback": settings.VOICE_BACKEND_PLAYBACK,
        "queue_size": vq.qsize() if vq else 0,
        "player": type(player).__name__ if player else None,
        "cache_size": getattr(getattr(request.app.state, "spotter_cache", None), "size", 0),
    }

    return {
        "status": "ok",
        "shared_memory": {
            "status": shm_status,
            "offline_mode": reader_offline,
            "last_lap": last_lap,
        },
        "telemetry": {
            "source": telemetry_source,
        },
        "spotter": spotter_info,
        "frontend_telemetry": {
            "received": getattr(request.app.state, "latest_client_frame", None) is not None,
        },
        "lmu_api": {
            "status": "active" if cache_info.get("drivers", 0) > 0 or cache_info.get("brakes", 0) > 0 else "idle",
            "cache": cache_info,
        },
        "llm": {"configured": llm_api_configured, "model": settings.LLM_MODEL},
        "asr": get_asr_status(),
        "race_loop": race_loop,
        "voice": voice,
    }
