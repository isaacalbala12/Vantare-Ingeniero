from __future__ import annotations

import logging
from collections.abc import Callable

from src.models.messages import AlertMessage, BaseMessage
from src.voice.play_command import play_command_from_alert
from src.voice.voice_queue import VoiceQueue

logger = logging.getLogger("vantare.voice_bridge")


class VoiceBridge:
    def __init__(
        self,
        *,
        ws_broadcast: Callable[[BaseMessage], None],
        voice_queue: VoiceQueue,
        enabled: bool = True,
    ) -> None:
        self._ws_broadcast = ws_broadcast
        self._queue = voice_queue
        self.enabled = enabled

    def send(self, message: BaseMessage) -> None:
        self._ws_broadcast(message)
        if not self.enabled or not isinstance(message, AlertMessage):
            return
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._enqueue_alert(message))
        except RuntimeError:
            logger.debug("VoiceBridge: no event loop — running enqueue synchronously")
            asyncio.run(self._enqueue_alert(message))

    async def _enqueue_alert(self, alert: AlertMessage) -> None:
        payload = alert.payload or {}
        event_id = str(payload.get("event_id") or alert.category)
        cmd = play_command_from_alert(
            text=alert.message,
            category=alert.category,
            audio_priority=alert.audio_priority,
            event_id=event_id,
            ttl_seconds=alert.ttl,
            payload=payload,
        )
        await self._queue.put(cmd)
        logger.debug("Enqueued PlayCommand %s %s", cmd.priority, cmd.event_id)
