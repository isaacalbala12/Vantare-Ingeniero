"""AudioQueueManager — dual queue system for CrewChief-style TTS events.

Two heaps: Immediate (spotter, critical) and Regular (normal alerts).
Event-driven via asyncio.Event instead of polling.
"""

import asyncio
import heapq
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from src.models.messages import QueuedMessage, SoundType, MessagePriority, AlertMessage, BaseMessage

logger = logging.getLogger("vantare.audio_queue")


class AudioQueueManager:
    def __init__(self, broadcast_callback=None) -> None:
        self._broadcast = broadcast_callback
        self._verbosity: int = 0
        self._keep_quiet: bool = False
        self._verbosity_min_priority = {0: 1, 5: 10, 10: 15, 20: 20}
        self._validators: Dict[str, Callable[[QueuedMessage, Dict[str, Any]], bool]] = {}
        self._immediate: List = []   # heap for urgent messages
        self._regular: List = []     # heap for normal messages
        self._lock: threading.Lock = threading.Lock()
        self._counter: int = 0
        self._latest_state: Dict[str, Any] = {}
        self._running: bool = False
        self._wake_event: asyncio.Event = asyncio.Event()

    def update_state(self, state: Dict[str, Any]) -> None:
        self._latest_state = state

    def register_validator(self, event_type: str,
                           validator: Callable[[QueuedMessage, Dict[str, Any]], bool]) -> None:
        self._validators[event_type] = validator

    def set_verbosity(self, level: int) -> None:
        self._verbosity = level

    def set_keep_quiet(self, enabled: bool) -> None:
        self._keep_quiet = enabled
        if enabled:
            with self._lock:
                self._immediate.clear()
                self._regular.clear()

    def enqueue(self, msg: QueuedMessage) -> None:
        """Enqueue a message and wake the consumer loop."""
        if self._keep_quiet and msg.sound_type not in (SoundType.SPOTTER, SoundType.CRITICAL):
            return
        min_p = self._verbosity_min_priority.get(self._verbosity, 1)
        if int(msg.priority) < min_p:
            return
        with self._lock:
            self._counter += 1
            entry = (-int(msg.priority), self._counter, msg)
            if msg.sound_type <= SoundType.IMPORTANT:
                heapq.heappush(self._immediate, entry)
            else:
                heapq.heappush(self._regular, entry)
        self._wake_event.set()

    def enqueue_alert(self, alert: AlertMessage) -> None:
        """Spotter express path: broadcast directly, bypass queue."""
        if self._broadcast:
            self._broadcast(alert)

    async def start(self) -> None:
        """Consumer loop — waits on asyncio.Event instead of polling."""
        self._running = True
        while self._running:
            try:
                await self._wake_event.wait()
                self._wake_event.clear()
                # Drain queue completely
                while self._running:
                    msg = self._dequeue_next()
                    if msg is None:
                        break
                    if not self._validate(msg):
                        continue
                    alert = AlertMessage(
                        event="alert",
                        alert_id=msg.message_id,
                        category=msg.event_type,
                        message=msg.text or "",
                        audio_priority=msg.priority.name,
                        priority=msg.priority,
                        sound_type=msg.sound_type,
                        severity="CRITICAL" if msg.priority >= MessagePriority.CRITICAL else "INFO",
                        ttl=int(msg.ttl_seconds) or 15,
                        dismissable=msg.sound_type >= SoundType.REGULAR,
                        audio_file_id=msg.audio_file_id,
                        payload={"priority": int(msg.priority), "sound_type": int(msg.sound_type)},
                    )
                    if self._broadcast:
                        self._broadcast(alert)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("AudioQueue error: %s", e, exc_info=True)
                await asyncio.sleep(0.5)

    async def stop(self) -> None:
        """Stop the consumer loop. Wakes the event so wait() exits."""
        self._running = False
        self._wake_event.set()
        with self._lock:
            self._immediate.clear()
            self._regular.clear()

    def _dequeue_next(self) -> Optional[QueuedMessage]:
        """Check both queues independently. Regular queue is checked even if immediate has future-due msg."""
        now = time.time()
        with self._lock:
            # Check immediate queue
            while self._immediate:
                neg_prio, order, msg = self._immediate[0]
                if msg.is_expired(now):
                    heapq.heappop(self._immediate)
                    continue
                if msg.is_due(now):
                    heapq.heappop(self._immediate)
                    return msg
                break
            # Check regular queue
            while self._regular:
                neg_prio, order, msg = self._regular[0]
                if msg.is_expired(now):
                    heapq.heappop(self._regular)
                    continue
                if msg.is_due(now):
                    heapq.heappop(self._regular)
                    return msg
                break
        return None

    def _validate(self, msg: QueuedMessage) -> bool:
        if msg.event_type and msg.event_type in self._validators:
            try:
                return self._validators[msg.event_type](msg, self._latest_state)
            except Exception as e:
                logger.warning("Validator error for %s: %s", msg.event_type, e)
        return True

    def interrupt(self, min_priority: SoundType = SoundType.SPOTTER) -> None:
        """Send audio_interrupt message as BaseMessage."""
        if self._broadcast:
            class AudioInterrupt(BaseMessage):
                event: str = "audio_interrupt"
                min_priority: int
            self._broadcast(AudioInterrupt(event="audio_interrupt", min_priority=int(min_priority)))
