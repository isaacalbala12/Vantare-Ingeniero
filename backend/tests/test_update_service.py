"""Tests para update_service."""

import pytest

from src.services import update_service


class TestUpdateService:
    def test_parse_version(self):
        assert update_service.parse_version("0.1.0") == (0, 1, 0)
        assert update_service.parse_version("v1.2.3") == (1, 2, 3)

    def test_is_newer_version(self):
        assert update_service.is_newer_version("0.2.0", "0.1.0") is True
        assert update_service.is_newer_version("0.1.0", "0.1.0") is False
        assert update_service.is_newer_version("0.1.0", "0.2.0") is False

    @pytest.mark.asyncio
    async def test_check_for_update_no_release(self, monkeypatch):
        async def fake_fetch(repo=None):
            return None

        monkeypatch.setattr(update_service, "fetch_latest_release", fake_fetch)
        result = await update_service.check_for_update("0.1.0")
        assert result["update_available"] is False

    @pytest.mark.asyncio
    async def test_check_for_update_newer_available(self, monkeypatch):
        async def fake_fetch(repo=None):
            return {"tag": "0.2.0", "name": "0.2.0", "html_url": "https://example.com/release"}

        monkeypatch.setattr(update_service, "fetch_latest_release", fake_fetch)
        result = await update_service.check_for_update("0.1.0")
        assert result["update_available"] is True
        assert result["latest_version"] == "0.2.0"
