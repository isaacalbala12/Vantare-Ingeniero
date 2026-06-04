"""Penalties — seguimiento de penalizaciones recibidas durante la sesión.

Eventos que dispara:
- penalties/penalty_received: cuando se detecta una nueva penalización
"""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents

logger = logging.getLogger("vantare.events.penalties")

C_PENALTY_RECEIVED = "penalties/penalty_received"


class Penalties(AbstractEvent):
    applicable_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW,
        SessionPhase.CHECKERED, SessionPhase.FORMATION,
    ]
    category = "ALL"
    sequence = 4

    def __init__(self, ap=None, audio_player=None) -> None:
        super().__init__(ap, audio_player)
        self._last_num_outstanding: int = 0

    def clear_state(self) -> None:
        self._last_num_outstanding = 0

    def trigger_internal(
        self, prev: Optional[GameStateData], curr: GameStateData
    ) -> None:
        if curr is None:
            return
        if self.should_suppress(curr):
            self._last_num_outstanding = curr.penalties.num_outstanding
            return

        num_outstanding = curr.penalties.num_outstanding

        # Detect new penalty: outstanding count increased
        if num_outstanding > self._last_num_outstanding:
            new_count = num_outstanding - self._last_num_outstanding
            penalty_type = self._describe_penalty(curr.penalties)
            self.play_message(QueuedMessage(
                C_PENALTY_RECEIVED, expires=15, priority=12,
                fragments=contents(f"penalty received: {penalty_type}"),
            ))
            logger.info(
                "Penalty detected: %d outstanding (was %d), type=%s",
                num_outstanding, self._last_num_outstanding, penalty_type,
            )

        # Also warn about high cut warnings
        cut_warnings = curr.penalties.cut_warnings
        if cut_warnings > 0 and cut_warnings % 5 == 0 and num_outstanding == self._last_num_outstanding:
            # Every 5 cut warnings, remind (unless there's already a penalty)
            pass  # Future: could add a cut warning message here

        self._last_num_outstanding = num_outstanding

    def _describe_penalty(self, penalties) -> str:
        """Return a human-readable description of the current penalty type."""
        if penalties.has_stop_go:
            return "stop and go"
        if penalties.has_drivethrough:
            return "drive through"
        if penalties.has_slow_down:
            return "slow down"
        if penalties.cut_warnings > 0:
            return "track limits"
        return "unknown"
