from __future__ import annotations

import uuid

from src.models.messages import AlertMessage

from .types import CrewChiefChannel, CrewChiefMessage


def _priority_to_audio_rank(message: CrewChiefMessage) -> str:
    return str(message.priority.rank)


def _category_for(message: CrewChiefMessage) -> str:
    if message.channel == CrewChiefChannel.SPOTTER:
        return "spotter"
    if message.channel == CrewChiefChannel.VOICE_RESPONSE:
        return "voice_response"
    return "engineer"


def map_message_to_alert(message: CrewChiefMessage, *, delayed_until_ms: int | None = None) -> AlertMessage:
    ttl_seconds = max(1, int(round(message.ttl_ms / 1000)))
    payload = dict(message.payload)
    payload.update(
        {
            "event_id": message.event_id,
            "queue_class": "IMMEDIATE" if message.immediate else "NORMAL",
            "ttl_ms": message.ttl_ms,
            "delay_ms": message.delay_ms,
            "play_even_when_silenced": message.play_even_when_silenced,
            "can_interrupt": message.can_interrupt,
            "validation_key": message.validation_key,
        }
    )
    if delayed_until_ms is not None and delayed_until_ms > 0:
        payload["delayed_until_ms"] = delayed_until_ms
    return AlertMessage(
        event="alert",
        alert_id=str(uuid.uuid4()),
        category=_category_for(message),
        message=message.text,
        audio_priority=_priority_to_audio_rank(message),
        severity=message.priority.value,
        ttl=ttl_seconds,
        dismissable=not message.play_even_when_silenced,
        payload=payload,
    )
