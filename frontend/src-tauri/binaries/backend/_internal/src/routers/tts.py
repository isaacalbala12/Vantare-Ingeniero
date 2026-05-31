import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response

from src.config import settings

logger = logging.getLogger("vantare.tts_router")

router = APIRouter()


@router.get("/tts")
async def synthesize_tts(request: Request, text: str = ""):
    """Convierte texto a audio usando el backend TTS configurado.

    Backends:
      - "edge":       Edge TTS (cloud) -> audio/mpeg
      - "piper":      Piper TTS (local) -> audio/wav
      - "elevenlabs": ElevenLabs TTS (cloud) -> audio/mpeg
      - "gemini":     Gemini TTS (cloud) -> audio/wav

    Si el backend configurado falla, intenta el otro como fallback automático.
    Uso: GET /tts?text=Hola%20piloto
    """
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Texto vacío")

    if len(text) > 2000:
        logger.warning("Texto TTS truncado de %d a 2000 caracteres", len(text))
        text = text[:1997] + "..."

    backend = settings.TTS_BACKEND
    services = _resolve_services(request.app.state)

    # Orden de fallback: intentar backends en orden, empezando por el configurado
    fallback_order = ["edge", "piper", "elevenlabs", "gemini"]
    # Rotar para que el backend configurado sea el primero
    if backend in fallback_order:
        idx = fallback_order.index(backend)
        fallback_order = fallback_order[idx:] + fallback_order[:idx]

    for candidate in fallback_order:
        service = services.get(candidate)
        if not service:
            continue
        audio_bytes, media_type = await _try_synthesize(service, candidate, text)
        if audio_bytes is not None:
            if candidate != backend:
                logger.warning("Fallback TTS: backend '%s' usado en lugar de '%s'", candidate, backend)
            return _build_response(audio_bytes, media_type, text)

    raise HTTPException(status_code=500, detail="Todos los backends TTS fallaron")


def _resolve_services(state) -> dict:
    """Devuelve un dict con los servicios TTS disponibles."""
    return {
        "edge": getattr(state, "edge_tts_service", None),
        "piper": getattr(state, "piper_tts_service", None),
        "elevenlabs": getattr(state, "elevenlabs_tts_service", None),
        "gemini": getattr(state, "gemini_tts_service", None),
    }


def _content_type(backend: str) -> str:
    return "audio/mpeg" if backend in ("edge", "elevenlabs") else "audio/wav"


async def _try_synthesize(service, backend: str, text: str):
    """Intenta sintetizar con un servicio. Retorna (bytes|None, media_type)."""
    if not service:
        return None, None
    try:
        audio = await service.synthesize(text)
        return audio, _content_type(backend)
    except Exception as e:
        logger.error("Error en TTS backend '%s': %s", backend, e)
        return None, None


def _build_response(audio_bytes: bytes, media_type: str, text: str) -> Response:
    return Response(
        content=audio_bytes,
        media_type=media_type,
        headers={
            "X-Response-Text": text.strip()[:500],
            "Content-Length": str(len(audio_bytes)),
        },
    )
