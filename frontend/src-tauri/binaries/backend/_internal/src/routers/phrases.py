"""REST endpoints para frases spotter/triggers editables."""

from __future__ import annotations

import logging

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel

from src.intelligence.phrase_picker import reload_picker
from src.persistence.phrase_store import PhraseStore

logger = logging.getLogger("vantare.phrases_router")

router = APIRouter(prefix="/phrases", tags=["phrases"])


class PhrasePayload(BaseModel):
    spotter: dict[str, Any] | None = None
    triggers: dict[str, Any] | None = None


def _spotter_profile_id(request: Request) -> str:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        return "standard"
    session = getattr(engine, "session", None) or {}
    if not isinstance(session, dict):
        return "standard"
    pid = str(session.get("personalityProfileId") or "standard").strip().lower()
    return pid if pid in ("standard", "formal", "aggressive") else "standard"


async def _warm_spotter_cache(request: Request) -> None:
    cache = getattr(request.app.state, "spotter_cache", None)
    edge = getattr(request.app.state, "edge_tts_service", None)
    routing = getattr(request.app.state, "tts_routing", None)
    if cache is None or edge is None:
        return
    voice = routing.edge_voice_spotter if routing is not None else None
    profile_id = _spotter_profile_id(request)
    try:
        cache.invalidate_all()
        await cache.warm(voice=voice, profile_id=profile_id)
        logger.info(
            "SpotterPhraseCache re-warmed after phrase update (%d entries, profile=%s)",
            cache.size,
            profile_id,
        )
    except Exception as exc:
        logger.warning("Spotter cache re-warm failed after phrase update: %s", exc)


def _store(request: Request) -> PhraseStore:
    store = getattr(request.app.state, "phrase_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="PhraseStore no disponible")
    return store


def _apply_phrase_save(
    store: PhraseStore,
    body: dict[str, Any],
    *,
    replace: bool,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    try:
        saved = store.save_user(body, replace=replace)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    reload_picker()
    background_tasks.add_task(_warm_spotter_cache, request)
    return {"saved": True, "user": saved, "replace": replace}


@router.get("")
async def get_phrases_merged(request: Request):
    store = _store(request)
    return store.load_merged()


@router.get("/meta")
async def get_phrases_meta(request: Request):
    store = _store(request)
    store.load_user()
    return {"user_load_error": store.last_user_load_error}


@router.get("/defaults")
async def get_phrases_defaults(request: Request):
    store = _store(request)
    return store.load_defaults()


@router.get("/export")
async def export_phrases(request: Request):
    store = _store(request)
    return store.export_user()


@router.put("")
async def save_phrases(
    payload: PhrasePayload,
    request: Request,
    background_tasks: BackgroundTasks,
    replace: bool = Query(False, description="Reemplazar overrides en lugar de fusionar"),
):
    store = _store(request)
    body = payload.model_dump(exclude_none=True)
    return _apply_phrase_save(store, body, replace=replace, request=request, background_tasks=background_tasks)


@router.post("/import")
async def import_phrases(
    payload: PhrasePayload,
    request: Request,
    background_tasks: BackgroundTasks,
    replace: bool = Query(False, description="Reemplazar todo el fichero usuario"),
):
    store = _store(request)
    body = payload.model_dump(exclude_none=True)
    return _apply_phrase_save(store, body, replace=replace, request=request, background_tasks=background_tasks)


@router.post("/reset")
async def reset_phrases(request: Request, background_tasks: BackgroundTasks):
    store = _store(request)
    store.reset_user()
    reload_picker()
    background_tasks.add_task(_warm_spotter_cache, request)
    return {"reset": True}


@router.delete("")
async def delete_user_phrases(request: Request, background_tasks: BackgroundTasks):
    return await reset_phrases(request, background_tasks)
