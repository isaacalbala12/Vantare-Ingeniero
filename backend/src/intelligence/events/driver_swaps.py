"""DriverSwaps — detecta cambios de piloto y tiempo de stint en endurance.

Eventos que dispara:
- driver_swaps/driver_change: cuando se produce un cambio de piloto
- driver_swaps/stint_30min: cuando el stint supera los 30 minutos
- driver_swaps/stint_45min: cuando el stint supera los 45 minutos
"""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents

logger = logging.getLogger("vantare.events.driver_swaps")

C_DRIVER_CHANGE = "driver_swaps/driver_change"
C_STINT_30MIN = "driver_swaps/stint_30min"
C_STINT_45MIN = "driver_swaps/stint_45min"

LMU_PIT_STOPPED = 3


class DriverSwaps(AbstractEvent):
    applicable_types = [SessionType.RACE]
    applicable_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW,
        SessionPhase.FORMATION, SessionPhase.COUNTDOWN,
    ]
    category = "ALL"
    sequence = 2

    def __init__(self, ap=None, audio_player=None) -> None:
        super().__init__(ap, audio_player)
        self._stint_start_time: float = 0.0
        self._last_30min_warn: bool = False
        self._last_45min_warn: bool = False
        self._last_pit_state: int = 0
        self._driver_swap_detected: bool = False

    def clear_state(self) -> None:
        self._stint_start_time = 0.0
        self._last_30min_warn = False
        self._last_45min_warn = False
        self._last_pit_state = 0
        self._driver_swap_detected = False

    def trigger_internal(
        self, prev: Optional[GameStateData], curr: GameStateData
    ) -> None:
        if curr is None:
            return
        if self.should_suppress(curr):
            self._last_pit_state = curr.pit.pit_state
            return

        pit_state = curr.pit.pit_state
        now = curr.now

        # Detect driver swap: transition INTO pit_state == 3 (PIT_STOPPED)
        # from a different state. This avoids re-triggering every tick.
        if pit_state == LMU_PIT_STOPPED and self._last_pit_state != LMU_PIT_STOPPED:
            self._stint_start_time = now
            self._last_30min_warn = False
            self._last_45min_warn = False
            self._driver_swap_detected = True
            self.play_message(QueuedMessage(
                C_DRIVER_CHANGE, expires=15, priority=10,
                fragments=contents("driver change"),
            ))

        # Reset flag when leaving pits
        if pit_state != LMU_PIT_STOPPED and self._driver_swap_detected:
            self._driver_swap_detected = False

        # Stint duration warnings (only when stint has started and we're not in pits)
        if self._stint_start_time > 0 and pit_state != LMU_PIT_STOPPED:
            elapsed = now - self._stint_start_time
            if elapsed > 2700 and not self._last_45min_warn:  # 45 min
                self.play_message(QueuedMessage(
                    C_STINT_45MIN, expires=10, priority=10,
                    fragments=contents("45 minute stint"),
                ))
                self._last_45min_warn = True
            elif elapsed > 1800 and not self._last_30min_warn:  # 30 min
                self.play_message(QueuedMessage(
                    C_STINT_30MIN, expires=10, priority=10,
                    fragments=contents("30 minute stint"),
                ))
                self._last_30min_warn = True

        self._last_pit_state = pit_state
