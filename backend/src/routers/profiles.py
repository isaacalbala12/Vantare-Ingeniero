"""REST endpoints para perfiles de configuración."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("vantare.profiles_router")

router = APIRouter(prefix="/profiles", tags=["profiles"])


class ProfilePayload(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


@router.get("")
async def list_profiles(request: Request):
    store = getattr(request.app.state, "profile_store", None)
    if store is None:
        return []
    return {"profiles": store.list_profiles()}


@router.get("/{name}")
async def get_profile(name: str, request: Request):
    store = getattr(request.app.state, "profile_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="ProfileStore no disponible")
    try:
        config = store.load_profile(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"name": name, "config": config}


@router.put("/{name}")
async def save_profile(name: str, payload: ProfilePayload, request: Request):
    store = getattr(request.app.state, "profile_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="ProfileStore no disponible")
    try:
        store.save_profile(name, payload.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info("Perfil guardado: %s", name)
    return {"name": name, "saved": True}


@router.delete("/{name}")
async def delete_profile(name: str, request: Request):
    store = getattr(request.app.state, "profile_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="ProfileStore no disponible")
    try:
        store.delete_profile(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info("Perfil eliminado: %s", name)
    return {"name": name, "deleted": True}
