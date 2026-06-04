"""RaceTime — informa del tiempo restante, mitad de carrera y momentos clave.

Eventos que dispara:
- race_time/halfway: cuando se completa la mitad de la carrera
- race_time/{N}_seconds: cuando quedan N segundos (3600, 1800, 900, 300, 60)
"""

import logging
from typing import Optional, Dict

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents

logger = logging.getLogger("vantare.events.race_time")

C_HALFWAY = "race_time/halfway"
C_MILESTONE_3600 = "race_time/3600_seconds"
C_MILESTONE_1800 = "race_time/1800_seconds"
C_MILESTONE_900 = "race_time/900_seconds"
C_MILESTONE_300 = "race_time/300_seconds"
C_MILESTONE_60 = "race_time/60_seconds"


class RaceTime(AbstractEvent):
    applicable_types = [SessionType.RACE]
    applicable_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW,
    ]
    category = "ALL"
    sequence = 3

    def __init__(self, ap=None, audio_player=None) -> None:
        super().__init__(ap, audio_player)
        self._halfway_reported: bool = False
        # Time remaining milestones in seconds: 1h, 30min, 15min, 5min, 1min
        self._milestones: Dict[float, bool] = {
            3600: False,
            1800: False,
            900: False,
            300: False,
            60: False,
        }
        self._prev_completed_laps: int = 0

    def clear_state(self) -> None:
        self._halfway_reported = False
        for k in self._milestones:
            self._milestones[k] = False
        self._prev_completed_laps = 0

    def trigger_internal(
        self, prev: Optional[GameStateData], curr: GameStateData
    ) -> None:
        if curr is None:
            return
        if self.should_suppress(curr):
            self._prev_completed_laps = curr.session.completed_laps
            return

        remaining = curr.session.session_time_remaining
        running = curr.session.session_running_time

        # Guard: no data yet
        if remaining <= 0:
            return

        # Halfway detection: triggered when completed_laps changes
        # and running_time >= total / 2
        if not self._halfway_reported:
            total = running + remaining
            if total > 0 and running >= total / 2:
                self.play_message(QueuedMessage(
                    C_HALFWAY, expires=15, priority=8,
                    fragments=contents("halfway"),
                ))
                self._halfway_reported = True

        # Time remaining milestones (descending order)
        for milestone in (3600, 1800, 900, 300, 60):
            if remaining <= milestone and not self._milestones[milestone]:
                minutes = milestone // 60
                self.play_message(QueuedMessage(
                    f"race_time/{milestone}_seconds", expires=10, priority=8,
                    fragments=contents(f"{minutes} minutes remaining"),
                ))
                self._milestones[milestone] = True

        self._prev_completed_laps = curr.session.completed_laps
