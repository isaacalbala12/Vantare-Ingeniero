"""REST endpoints para grabación y reproducción de traces."""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("vantare.traces_router")

router = APIRouter(prefix="/traces", tags=["traces"])


class StartRecordingPayload(BaseModel):
    trace_id: Optional[str] = Field(default=None, max_length=80)


@router.get("")
async def list_traces(request: Request):
    store = getattr(request.app.state, "trace_store", None)
    if store is None:
        return {"traces": []}
    return {"traces": store.list_traces(), "recording": store.is_recording}


@router.post("/start")
async def start_recording(request: Request, payload: StartRecordingPayload | None = None):
    store = getattr(request.app.state, "trace_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="TraceStore no disponible")
    trace_id = payload.trace_id if payload else None
    try:
        tid = store.start_recording(trace_id)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    request.app.state.trace_playback_active = False
    logger.info("Trace recording started: %s", tid)
    return {"trace_id": tid, "recording": True}


@router.post("/stop")
async def stop_recording(request: Request):
    store = getattr(request.app.state, "trace_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="TraceStore no disponible")
    tid = store.stop_recording()
    return {"trace_id": tid, "recording": False}


@router.post("/{trace_id}/playback")
async def start_playback(
    trace_id: str,
    request: Request,
    speed: float = Query(default=1.0, gt=0, le=10),
):
    store = getattr(request.app.state, "trace_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="TraceStore no disponible")

    existing = getattr(request.app.state, "trace_playback_task", None)
    if existing and not existing.done():
        raise HTTPException(status_code=409, detail="Ya hay una reproducción en curso")

    async def inject(frame: dict) -> None:
        request.app.state.latest_client_frame = frame
        request.app.state.trace_playback_active = True

    async def _run() -> None:
        try:
            count = await store.playback(trace_id, inject, speed=speed)
            logger.info("Trace playback finished: %s (%d frames)", trace_id, count)
        except FileNotFoundError:
            logger.warning("Trace no encontrado para playback: %s", trace_id)
        finally:
            request.app.state.trace_playback_active = False

    task = asyncio.create_task(_run())
    request.app.state.trace_playback_task = task
    return {"trace_id": trace_id, "speed": speed, "status": "started"}


@router.post("/playback/stop")
async def stop_playback(request: Request):
    task = getattr(request.app.state, "trace_playback_task", None)
    if task and not task.done():
        task.cancel()
        request.app.state.trace_playback_active = False
        return {"status": "stopped"}
    return {"status": "idle"}
