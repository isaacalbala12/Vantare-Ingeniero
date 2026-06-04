"""Auth router: license key configuration and status endpoints."""
import logging

from fastapi import APIRouter, Request

from src.auth.license_provider import LicenseKeyProvider
from src.config import settings

logger = logging.getLogger("vantare.auth")

router = APIRouter(prefix="/api")


@router.post("/config")
async def set_license_key(data: dict, request: Request):
    """Validate and store a license key.

    Body: {"license_key": "..."}
    Returns: {"success": bool, "error": str?}
    """
    license_key = (data.get("license_key") or "").strip()
    if not license_key:
        return {"success": False, "error": "license_key required"}

    # Get or create the license provider
    provider = getattr(request.app.state, "license_provider", None)
    if provider is None:
        provider = LicenseKeyProvider(worker_url=settings.WORKER_URL)
        request.app.state.license_provider = provider

    result = await provider.validate(license_key)
    if result.is_valid:
        # Store in app state
        request.app.state.license_key = license_key

        # Also update the module-level key in VLLMClient
        from src.intelligence.llm_client import set_license_key as set_llm_key
        set_llm_key(license_key)

        logger.info("License key configured (prefix=%s...)", license_key[:8])
        return {"success": True}
    else:
        logger.warning("License key rejected: error_code=%s", result.error_code)
        return {"success": False, "error": result.error_code}


@router.get("/auth/status")
async def auth_status(request: Request):
    """Return current auth status. Never 500s.

    Returns: {"valid": bool, "key_prefix": str}
    """
    try:
        license_key = getattr(request.app.state, "license_key", "") or ""
        return {
            "valid": bool(license_key),
            "key_prefix": license_key[:8] + "..." if license_key else "",
        }
    except Exception as exc:
        logger.error("Unexpected error in auth/status: %s", exc)
        return {"valid": False, "key_prefix": ""}
