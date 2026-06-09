"""Tests de update_service."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services import update_service


@pytest.mark.asyncio
async def test_fetch_latest_release_logs_debug_on_network_error(caplog):
    with patch("src.services.update_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.side_effect = OSError("network down")
        mock_client_cls.return_value = mock_client

        with caplog.at_level("DEBUG", logger="vantare.update"):
            result = await update_service.fetch_latest_release()

    assert result is None
    assert any("fetch_latest_release failed" in r.message for r in caplog.records)
