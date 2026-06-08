"""LEGACY ruta B (batch LLM). Post Task 48: desactivado por defecto.

Mensajes deterministas → CrewChiefEventSuite @ 20 Hz.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from src.intelligence.event_registry import get_event
from src.intelligence.personality_pack import PersonalityPack
from src.intelligence.verbosity_controller import VerbosityController
from src.models.messages import CommentaryEndMessage

logger = logging.getLogger("vantare.commentary")


@dataclass
class PendingCommentaryEvent:
    event_id: str
    summary: str
    priority: str
    payload: Dict[str, Any] = field(default_factory=dict)


class CommentaryOrchestrator:
    """Agrupa eventos de narración y emite un único commentary_end tras debounce."""

    def __init__(
        self,
        broadcast_callback: Optional[Callable[[Any], None]] = None,
        verbosity: Optional[VerbosityController] = None,
        personality: Optional[PersonalityPack] = None,
        debounce_s: float = 3.0,
        max_wait_s: float = 8.0,
        llm_complete: Optional[Callable[[str], Awaitable[str]]] = None,
    ) -> None:
        self._broadcast = broadcast_callback
        self._verbosity = verbosity or VerbosityController()
        self._personality = personality or PersonalityPack()
        self._debounce_s = debounce_s
        self._max_wait_s = max_wait_s
        self._pending: List[PendingCommentaryEvent] = []
        self._flush_task: Optional[asyncio.Task] = None
        self._llm_complete = llm_complete
        self._first_pending_at: Optional[float] = None

    @property
    def verbosity(self) -> VerbosityController:
        return self._verbosity

    @property
    def personality(self) -> PersonalityPack:
        return self._personality

    def pending_count(self) -> int:
        return len(self._pending)

    def enqueue(
        self,
        event_id: str,
        summary: str,
        priority: str | None = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Encola un evento de comentario. Devuelve False si la verbosidad lo filtra."""
        if self._verbosity.speak_only_when_spoken_to:
            logger.debug("Commentary filtrado por speak-only: %s", event_id)
            return False
        event_def = get_event(event_id)
        eff_priority = priority or (event_def.priority if event_def else "NORMAL")
        verbosity_min = event_def.verbosity_min if event_def else eff_priority
        if not self._verbosity.should_emit_event(verbosity_min):
            logger.debug("Commentary filtrado por verbosidad: %s", event_id)
            return False
        if not summary or not summary.strip():
            return False

        new_event = PendingCommentaryEvent(
            event_id=event_id,
            summary=summary.strip(),
            priority=eff_priority,
            payload=payload or {},
        )
        for idx, existing in enumerate(self._pending):
            if existing.event_id == event_id:
                self._pending[idx] = new_event
                break
        else:
            self._pending.append(new_event)
            if self._first_pending_at is None:
                self._first_pending_at = time.monotonic()

        self._schedule_flush()
        return True

    def _schedule_flush(self) -> None:
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.debug("Commentary debounce omitido: no hay event loop activo")
            return
        self._flush_task = loop.create_task(self._debounced_flush())

    async def _debounced_flush(self) -> None:
        try:
            if self._first_pending_at is not None:
                elapsed = time.monotonic() - self._first_pending_at
                wait = min(self._debounce_s, max(0.0, self._max_wait_s - elapsed))
            else:
                wait = self._debounce_s
            if wait > 0:
                await asyncio.sleep(wait)
            await self.flush()
        except asyncio.CancelledError:
            pass

    async def flush(self) -> Optional[CommentaryEndMessage]:
        if not self._pending:
            return None
        batch = self._pending[:]
        self._pending.clear()
        self._first_pending_at = None
        text = await self._format_batch_async(batch)
        if not text:
            return None
        source_events = [e.event_id for e in batch]
        top_priority = max(batch, key=lambda e: _priority_rank(e.priority)).priority
        msg = CommentaryEndMessage(
            event="commentary_end",
            commentary_id=str(uuid.uuid4()),
            full_text=text,
            category="commentary",
            audio_priority=top_priority,
            source_events=source_events,
            profile_id=self._personality.profile_id,
        )
        if self._broadcast:
            self._broadcast(msg)
        return msg

    async def _format_batch_async(self, batch: List[PendingCommentaryEvent]) -> str:
        from src.intelligence.commentary_llm_formatter import format_commentary_batch

        events = [(e.event_id, e.summary, e.priority) for e in batch]
        return await format_commentary_batch(
            events,
            self._personality.engineer_system_suffix(),
            llm_complete=self._llm_complete,
        )

    def _format_batch(self, batch: List[PendingCommentaryEvent]) -> str:
        """Sync fallback for tests that call _format_batch directly."""
        from src.intelligence.commentary_llm_formatter import format_batch_deterministic

        events = [(e.event_id, e.summary, e.priority) for e in batch]
        return format_batch_deterministic(events, self._personality.engineer_system_suffix())


def _priority_rank(priority: str) -> int:
    return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get((priority or "LOW").upper(), 1)
