"""Opponents — seguimiento de gaps y posiciones de rivales.

Eventos que dispara:
- opponents/gap_ahead: gap al coche de delante (máx cada 30s)
"""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents

logger = logging.getLogger("vantare.events.opponents")

_GAP_REPORT_INTERVAL = 30.0  # Segundos mínimo entre reportes de gap


class Opponents(AbstractEvent):
    applicable_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE,
    ]
    applicable_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW,
    ]
    category = "ALL"
    sequence = 12

    def __init__(self, ap=None, audio_player=None) -> None:
        super().__init__(ap, audio_player)
        self._last_gap_report: float = 0.0

    def trigger_internal(
        self, prev: Optional[GameStateData], curr: GameStateData
    ) -> None:
        if curr is None or not curr.opponents:
            return

        now = curr.now
        if now - self._last_gap_report < _GAP_REPORT_INTERVAL:
            return

        # Find closest opponent ahead
        gaps = [(opp.delta, name) for name, opp in curr.opponents.items()]
        gaps.sort()
        ahead = [g for g in gaps if g[0] > 0]

        if ahead:
            self.play(QueuedMessage(
                "opponents/gap_ahead", expires=10, priority=8,
                fragments=contents(f"gap to car ahead {ahead[0][0]:.1f}"),
            ))

        self._last_gap_report = now

    def clear_state(self) -> None:
        self._last_gap_report = 0.0
