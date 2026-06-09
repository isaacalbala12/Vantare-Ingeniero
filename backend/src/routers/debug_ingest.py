"""Ingesta NDJSON de logs de debug del frontend (sesión agente)."""
from pathlib import Path

from fastapi import APIRouter, Request

router = APIRouter(tags=["debug"])
_LOG_PATH = Path(__file__).resolve().parents[3] / "debug-69c028.log"


@router.post("/debug/ingest")
async def debug_ingest(request: Request) -> dict:
    body = await request.body()
    if body:
        with _LOG_PATH.open("ab") as f:
            f.write(body.strip() + b"\n")
    return {"ok": True}
