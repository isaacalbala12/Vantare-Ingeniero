from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import time

from src.models.messages import AlertMessage


class RaceEvent(ABC):
    """Base class for deterministic race events with cooldown and dedup."""

    def __init__(self, broadcast_callback=None) -> None:
        self.broadcast_callback = broadcast_callback
        # cooldown tracking: event_type -> last_fired_timestamp
        self._last_fired: Dict[str, float] = {}
        # per-type cooldown seconds (can be overridden by subclasses)
        self.cooldowns: Dict[str, float] = {}
        # prevent duplicate alerts within the same evaluation tick
        self._fired_in_tick: set = set()

    def can_fire(self, event_type: str, min_interval_seconds: float) -> bool:
        now = time.time()
        last = self._last_fired.get(event_type, 0.0)
        return (now - last) >= min_interval_seconds

    def mark_fired(self, event_type: str) -> None:
        self._last_fired[event_type] = time.time()
        self._fired_in_tick.add(event_type)

    def reset_tick(self) -> None:
        self._fired_in_tick.clear()

    def fire(
        self,
        event_type: str,
        alert: AlertMessage,
        min_interval_seconds: float,
    ) -> None:
        if not self.can_fire(event_type, min_interval_seconds):
            return
        if event_type in self._fired_in_tick:
            return
        self.mark_fired(event_type)
        if self.broadcast_callback:
            self.broadcast_callback(alert)

    @abstractmethod
    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        """Evaluate telemetry state and return alerts."""
        ...

    def is_applicable(self, session_type: str, session_phase: str) -> bool:
        """Override in subclass to restrict event to specific session types/phases.
        Default: always applicable."""
        return True

    def reset_session(self) -> None:
        """Reset all internal state when a new session begins.
        Default clears cooldowns and fired-in-tick sets."""
        self._last_fired.clear()
        self._fired_in_tick.clear()

    def is_message_still_valid(
        self,
        event_type: str,
        current_state: dict,
        snapshot: Optional[dict] = None,
    ) -> bool:
        """Called by EventAdapter validator to check if a queued message is still relevant.
        Override in subclass for time-sensitive messages. Default returns True."""
        return True
