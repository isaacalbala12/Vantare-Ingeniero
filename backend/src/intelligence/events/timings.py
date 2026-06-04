"""Timings — tiempos de vuelta y sector.

Eventos que dispara:
- timings/personal_best: cuando el piloto marca su mejor vuelta personal
"""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents

logger = logging.getLogger("vantare.events.timings")


class Timings(AbstractEvent):
    applicable_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE,
    ]
    applicable_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW,
    ]
    category = "ALL"
    sequence = 14

    def __init__(self, audio_player=None) -> None:
        super().__init__(audio_player=audio_player)

    def trigger_internal(
        self, prev: Optional[GameStateData], curr: GameStateData
    ) -> None:
        if curr is None or prev is None:
            return

        # Report personal best lap
        if (
            curr.session.is_new_lap
            and curr.session.player_lap_time_prev > 0
            and curr.session.player_lap_time_best > 0
            and curr.session.player_lap_time_prev < curr.session.player_lap_time_best
        ):
            self.play(QueuedMessage(
                "timings/personal_best", expires=10, priority=10,
                fragments=contents("personal best lap"),
            ))

    def clear_state(self) -> None:
        pass
