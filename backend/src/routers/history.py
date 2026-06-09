"""
REST endpoint para el historial de consumo de combustible.

GET /history → List[{"lap": int, "consumption": float, "fuelRemaining": float, "lapTime": float}]
"""

import logging

from fastapi import APIRouter, Request

logger = logging.getLogger("vantare.history_router")

router = APIRouter()


@router.get("/history")
async def get_history(request: Request):
    """Devuelve el historial de consumo ordenado por vuelta."""
    store = getattr(request.app.state, "history_store", None)
    if store is None:
        logger.warning("HistoryStore no disponible en app.state")
        return []
    return store.get_history()
