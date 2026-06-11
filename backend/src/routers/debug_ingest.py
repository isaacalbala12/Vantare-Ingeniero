"""Ingesta NDJSON de logs de debug del frontend (sesión agente)."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from src.config import settings
from src.models.messages import AlertMessage

router = APIRouter(tags=["debug"])
_LOG_PATH = Path(__file__).resolve().parents[3] / "debug-69c028.log"


@router.post("/debug/ingest")
async def debug_ingest(request: Request) -> dict:
    body = await request.body()
    if body:
        with _LOG_PATH.open("ab") as f:
            f.write(body.strip() + b"\n")
    return {"ok": True}


@router.post("/debug/inject_alert")
async def inject_alert(request: Request) -> dict:
    """Inject a synthetic alert via WebSocket broadcast (DEBUG only, VC-R02)."""
    if not settings.debug:
        raise HTTPException(404, "Not found")
    body = await request.json()
    # Lazy import to avoid circular dependency at module load
    from src.routers.websocket import manager

    alert = AlertMessage(
        event="alert",
        alert_id=str(uuid.uuid4()),
        category=body.get("category", "proximity"),
        message=body.get("message", "Debug alert"),
        audio_priority=body.get("audio_priority", "2"),
        severity=body.get("severity", "INFO"),
        ttl=8,
        dismissable=True,
        payload={"service": body.get("service", "spotter")},
    )
    await manager.broadcast(alert)
    return {"ok": True}
