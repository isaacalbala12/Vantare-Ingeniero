"""EventAdapter — wraps existing RaceEvent instances to work with AudioQueueManager.

Converts AlertMessage outputs from existing events into QueuedMessage for
the AudioQueueManager. Handles the dual audio_priority encoding scheme
(semantic strings vs integer strings from spotter/position events).
"""

import logging
import time
from typing import Any, Dict, List, Optional

from src.intelligence.events.base_event import RaceEvent
from src.services.audio_queue import AudioQueueManager
from src.models.messages import AlertMessage, QueuedMessage, SoundType, MessagePriority

logger = logging.getLogger("vantare.event_adapter")

# audio_priority has TWO encoding schemes across the codebase:
#   - Semantic strings: "CRITICAL", "HIGH", "MEDIUM", "LOW" (fuel.py, engine.py, flags.py, etc.)
#   - Integer strings:  "4"=critical, "3"=high, "2"=medium, "1"=low (spotter.py, position.py)
# _normalize_priority() handles both formats.

_INT_PRIORITY_MAP = {
    "4": (SoundType.CRITICAL, MessagePriority.CRITICAL),
    "3": (SoundType.IMPORTANT, MessagePriority.HIGH),
    "2": (SoundType.REGULAR, MessagePriority.MEDIUM),
    "1": (SoundType.REGULAR, MessagePriority.LOW),
}

_STR_PRIORITY_MAP = {
    "CRITICAL": (SoundType.CRITICAL, MessagePriority.CRITICAL),
    "HIGH": (SoundType.IMPORTANT, MessagePriority.HIGH),
    "MEDIUM": (SoundType.REGULAR, MessagePriority.MEDIUM),
    "LOW": (SoundType.REGULAR, MessagePriority.LOW),
    "SPOTTER": (SoundType.SPOTTER, MessagePriority.CRITICAL),
}


def _normalize_priority(audio_priority: str) -> tuple[SoundType, MessagePriority]:
    """Normalize both semantic and integer-string audio_priority values."""
    upper = audio_priority.strip().upper()
    result = _INT_PRIORITY_MAP.get(upper)
    if result:
        return result
    result = _STR_PRIORITY_MAP.get(upper)
    if result:
        return result
    logger.warning("Unknown audio_priority '%s', defaulting to REGULAR/MEDIUM", audio_priority)
    return (SoundType.REGULAR, MessagePriority.MEDIUM)


class EventAdapter:
    """Wraps existing RaceEvent instances to work with AudioQueueManager."""

    def __init__(self, audio_queue: AudioQueueManager) -> None:
        self.audio_queue = audio_queue

    def adapt_event(self, event: RaceEvent) -> None:
        """Register validators for all event types in this event's cooldowns."""
        for event_type in event.cooldowns:
            self.audio_queue.register_validator(
                event_type,
                lambda msg, state, et=event_type, ev=event:
                    self._validate_message(et, msg, state, ev)
            )

    def _validate_message(self, event_type: str, msg: QueuedMessage, state: Dict[str, Any], event: RaceEvent) -> bool:
        """Call event's is_message_still_valid if it exists, else True."""
        if hasattr(event, 'is_message_still_valid'):
            try:
                return event.is_message_still_valid(event_type, state, msg.session_data_snapshot)
            except Exception as e:
                logger.warning("Validator error for %s: %s", event_type, e)
        return True

    def process_event_output(self, event: RaceEvent, alerts: List[AlertMessage]) -> None:
        """Convert AlertMessages from an event into QueuedMessages and enqueue them."""
        for alert in alerts:
            queued = self._alert_to_queued(alert)
            if queued:
                self.audio_queue.enqueue(queued)

    def _alert_to_queued(self, alert: AlertMessage) -> Optional[QueuedMessage]:
        """Convert AlertMessage to QueuedMessage with proper priority mapping."""
        sound_type, priority = _normalize_priority(alert.audio_priority)
        return QueuedMessage(
            message_id=alert.alert_id,
            text=alert.message,
            audio_file_id=getattr(alert, 'audio_file_id', None),
            sound_type=sound_type,
            priority=priority,
            ttl_seconds=float(alert.ttl or 15),
            due_time=0.0,  # Immediate
            event_type=alert.event,
            session_data_snapshot=alert.payload if alert.payload else {},
            created_at=time.time(),
        )
