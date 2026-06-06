"""Tests MQTT service (Wave 6 — Task 22)."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.mqtt_service import MqttService


@pytest.mark.asyncio
async def test_publish_skipped_when_disabled(monkeypatch):
    monkeypatch.setattr("src.services.mqtt_service.settings.MQTT_ENABLED", False)
    svc = MqttService()
    await svc.publish_telemetry({"speed": 80})


@pytest.mark.asyncio
async def test_publish_when_enabled(monkeypatch):
    monkeypatch.setattr("src.services.mqtt_service.settings.MQTT_ENABLED", True)
    monkeypatch.setattr("src.services.mqtt_service.settings.MQTT_BROKER", "localhost")
    monkeypatch.setattr("src.services.mqtt_service.settings.MQTT_PORT", 1883)
    monkeypatch.setattr("src.services.mqtt_service.settings.MQTT_TOPIC", "vantare/telemetry")

    mock_client = MagicMock()
    with patch.object(MqttService, "_ensure_client", return_value=True):
        svc = MqttService()
        svc._client = mock_client
        await svc.publish_telemetry({"speed": 72, "fuel_in_tank": 40})
    mock_client.publish.assert_called_once()
