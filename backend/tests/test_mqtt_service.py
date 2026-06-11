import asyncio
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
    monkeypatch.setattr("src.services.mqtt_service.settings.ENABLE_MQTT", True)
    monkeypatch.setattr("src.services.mqtt_service.settings.BETA_SLIM", False)
    monkeypatch.setattr("src.services.mqtt_service.settings.MQTT_BROKER", "localhost")
    monkeypatch.setattr("src.services.mqtt_service.settings.MQTT_PORT", 1883)
    monkeypatch.setattr("src.services.mqtt_service.settings.MQTT_TOPIC", "vantare/telemetry")

    mock_client = MagicMock()
    with patch.object(MqttService, "_ensure_client", return_value=True):
        svc = MqttService()
        svc._client = mock_client
        await svc.publish_telemetry({"speed": 72, "fuel_in_tank": 40})
    mock_client.publish.assert_called_once()


@pytest.mark.asyncio
async def test_enqueue_keeps_only_latest_frame(monkeypatch):
    monkeypatch.setattr("src.services.mqtt_service.settings.MQTT_ENABLED", True)
    monkeypatch.setattr("src.services.mqtt_service.settings.ENABLE_MQTT", True)
    monkeypatch.setattr("src.services.mqtt_service.settings.BETA_SLIM", False)
    svc = MqttService()
    publish_calls = []

    async def fake_publish(frame):
        publish_calls.append(dict(frame))
        await asyncio.sleep(0.05)

    svc.publish_telemetry = fake_publish  # type: ignore[method-assign]

    svc.enqueue_telemetry({"speed": 1})
    svc.enqueue_telemetry({"speed": 2})
    svc.enqueue_telemetry({"speed": 3})

    await asyncio.sleep(0.2)
    await svc.shutdown_worker()

    assert len(publish_calls) == 1
    assert publish_calls[0]["speed"] == 3
