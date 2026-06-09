"""Monitores proactivos legacy — post Task 48 solo estado interno (comeback pearl)."""

from __future__ import annotations

from typing import Any, Callable, Optional

from src.intelligence.immediate_alert import ProactiveOutput
from shared_telemetry.session_kind import sync_session_fields


class ProactiveMonitorSuite:
    """Mantiene estado de sesión para perlas; emisiones CC @ 20 Hz."""

    def __init__(self, verbosity_should_emit: Optional[Callable[[str], bool]] = None) -> None:
        self._verbosity_should_emit = verbosity_should_emit or (lambda _p: True)
        self.reset_session()

    def reset_session(self) -> None:
        self._last_standing: Optional[int] = None
        self._last_class_position: Optional[int] = None
        self._last_lap = 0
        self._worst_position = None
        self._comeback_emitted = False

    def evaluate(
        self,
        telemetry: dict,
        strategy: dict,
        session: dict,
        *,
        history_store=None,
        strategy_service=None,
    ) -> list[ProactiveOutput]:
        telemetry, session = sync_session_fields(telemetry, session)
        events: list[ProactiveOutput] = []

        if telemetry.get("session_over") or session.get("session_over"):
            return events

        lap = int(telemetry.get("lap_number", 0) or 0)
        standing = telemetry.get("standing_position")
        if standing is not None:
            self._last_standing = int(standing)
            if self._worst_position is None or int(standing) > self._worst_position:
                self._worst_position = int(standing)

        class_pos = telemetry.get("class_position")
        if class_pos is not None:
            self._last_class_position = int(class_pos)

        self._last_lap = lap
        return events

    def check_comeback_pearl(self, standing: int) -> bool:
        """True si conviene emitir perla COMEBACK (posición recuperada desde peor)."""
        if self._comeback_emitted or self._worst_position is None:
            return False
        if standing < self._worst_position - 1:
            self._comeback_emitted = True
            return True
        return False
