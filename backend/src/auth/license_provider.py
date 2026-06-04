"""Validador de license keys contra el Worker Cloudflare."""
import asyncio
import logging
import time
from typing import Optional

from src.auth.protocol import AuthProvider, ProviderResult

logger = logging.getLogger("vantare.auth.license_provider")

CACHE_TTL = 300  # 5 minutes


class LicenseKeyProvider(AuthProvider):
    def __init__(self, worker_url: str, cache_ttl: int = CACHE_TTL):
        self._worker_url = worker_url.rstrip("/") + "/v1/chat/completions"
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[ProviderResult, float]] = {}  # key -> (result, cached_at)

    async def validate(self, token: str) -> ProviderResult:
        # Check cache first
        now = time.monotonic()
        cached = self._cache.get(token)
        if cached and (now - cached[1]) < self._cache_ttl:
            return cached[0]

        # Validate against Worker
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self._worker_url,
                    headers={"X-License-Key": token},
                    json={"model": "test", "messages": [{"role": "user", "content": "ping"}]},
                )
                if resp.status_code == 200:
                    result = ProviderResult(is_valid=True, license_key=token)
                elif resp.status_code == 401:
                    result = ProviderResult(is_valid=False, error_code="invalid_key")
                elif resp.status_code == 429:
                    result = ProviderResult(is_valid=False, error_code="rate_limited")
                else:
                    result = ProviderResult(is_valid=False, error_code="server_error")
        except Exception as e:
            logger.warning(f"Worker unreachable: {e}")
            result = ProviderResult(is_valid=False, error_code="server_error")

        self._cache[token] = (result, now)
        return result

    def invalidate_cache(self, token: str) -> None:
        self._cache.pop(token, None)
