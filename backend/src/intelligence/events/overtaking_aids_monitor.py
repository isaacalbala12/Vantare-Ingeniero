"""OvertakingAidsMonitor — monitorea DRS y Push-to-Pass.

Eventos que dispara:
- overtaking_aids/drs_enabled: cuando DRS se activa por primera vez en la sesión
"""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents

logger = logging.getLogger("vantare.events.overtaking_aids")


class OvertakingAidsMonitor(AbstractEvent):
    applicable_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE,
    ]
    applicable_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW,
    ]
    category = "ALL"
    sequence = 8

    def __init__(self, audio_player=None) -> None:
        super().__init__(audio_player=audio_player)
        self._drs_enabled_reported: bool = False

    def trigger_internal(
        self, prev: Optional[GameStateData], curr: GameStateData
    ) -> None:
        if curr is None:
            return

        drs = curr.overtaking.drs_enabled

        if drs and not self._drs_enabled_reported:
            self.play(QueuedMessage(
                "overtaking_aids/drs_enabled", expires=10, priority=10,
                fragments=contents("drs enabled"),
            ))
            self._drs_enabled_reported = True
        elif not drs:
            self._drs_enabled_reported = False

    def clear_state(self) -> None:
        self._drs_enabled_reported = False
