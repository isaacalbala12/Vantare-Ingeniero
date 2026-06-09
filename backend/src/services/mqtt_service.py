"""Publicación MQTT opt-in de telemetría seleccionada."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from src.config import settings

logger = logging.getLogger("vantare.mqtt")


class MqttService:
    """Publicador asíncrono hacia broker MQTT local (opt-in)."""

    def __init__(self) -> None:
        self._client: Any = None
        self._connected = False
        self._pending_frame: dict | None = None
        self._worker_task: asyncio.Task | None = None
        self._wake = asyncio.Event()

    def enqueue_telemetry(self, frame: dict) -> None:
        """Encola el frame más reciente; descarta frames anteriores no publicados."""
        if not self.enabled:
            return
        self._pending_frame = frame
        self._ensure_worker()
        self._wake.set()

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._wake = asyncio.Event()
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            frame = self._pending_frame
            self._pending_frame = None
            if frame is None:
                continue
            try:
                await self.publish_telemetry(frame)
            except Exception as e:
                logger.warning("MQTT publish failed: %s", e)
            if self._pending_frame is not None:
                self._wake.set()

    async def shutdown_worker(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    @property
    def enabled(self) -> bool:
        return bool(settings.MQTT_ENABLED)

    def _ensure_client(self) -> bool:
        if not self.enabled:
            return False
        if self._client is not None:
            return True
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.warning("paho-mqtt no instalado; MQTT desactivado")
            return False

        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        try:
            client.connect(settings.MQTT_BROKER, settings.MQTT_PORT, keepalive=30)
            client.loop_start()
            self._client = client
            self._connected = True
            logger.info("MQTT conectado a %s:%s", settings.MQTT_BROKER, settings.MQTT_PORT)
            return True
        except Exception as e:
            logger.warning("MQTT no disponible: %s", e)
            self._client = None
            self._connected = False
            return False

    def _select_fields(self, frame: dict) -> dict:
        return {
            "fuel_in_tank": frame.get("fuel_in_tank"),
            "speed": frame.get("speed"),
            "standing_position": frame.get("standing_position"),
            "lap_number": frame.get("lap_number"),
            "lap_distance": frame.get("lap_distance"),
            "tyre_wear_fl": frame.get("tyre_wear_fl"),
            "tyre_wear_fr": frame.get("tyre_wear_fr"),
            "tyre_wear_rl": frame.get("tyre_wear_rl"),
            "tyre_wear_rr": frame.get("tyre_wear_rr"),
        }

    async def publish_telemetry(self, frame: dict) -> None:
        if not self.enabled:
            return
        if not self._ensure_client():
            return
        payload = json.dumps(self._select_fields(frame), ensure_ascii=False)
        topic = settings.MQTT_TOPIC

        def _publish() -> None:
            if self._client:
                self._client.publish(topic, payload, qos=0)

        await asyncio.to_thread(_publish)

    def shutdown(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            self._worker_task = None
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
            self._connected = False


_mqtt_service: MqttService | None = None


def get_mqtt_service() -> MqttService:
    global _mqtt_service
    if _mqtt_service is None:
        _mqtt_service = MqttService()
    return _mqtt_service
