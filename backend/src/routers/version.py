"""REST endpoints de versión y comprobación de actualizaciones."""

import logging

from fastapi import APIRouter
from src.services.update_service import check_for_update
from src.version import APP_VERSION, GITHUB_REPO

logger = logging.getLogger("vantare.version_router")

router = APIRouter(tags=["version"])


@router.get("/version")
async def get_version():
    return {
        "version": APP_VERSION,
        "backend": APP_VERSION,
        "github_repo": GITHUB_REPO,
    }


@router.get("/version/check")
async def get_version_check():
    result = await check_for_update(APP_VERSION)
    return result
