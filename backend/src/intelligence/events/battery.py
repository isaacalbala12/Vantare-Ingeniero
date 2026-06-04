"""BatteryEvent — Gestion de Virtual Energy para Hypercars."""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents
from src.intelligence.event_flags import event_flags

logger = logging.getLogger("vantare.battery")

_LOW_VE_PCT = 25
_CRITICAL_VE_PCT = 10
_MIN_SAMPLES = 3


class BatteryEvent(AbstractEvent):
    applicable_session_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_session_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW
    ]
    message_category = "BATTERY"
    sequence = 25

    def __init__(self, audio_player=None):
        super().__init__(audio_player=audio_player)
        self._ve_samples: list = []
        self._announced_low: bool = False
        self._announced_critical: bool = False
        self._last_ve_pct: float = -1.0
        self._last_lap: int = -1
        self._avg_consumption: float = 0.0

    def trigger_internal(
        self, previous: Optional[GameStateData], current: GameStateData
    ) -> None:
        if current is None:
            return

        battery = current.battery
        ve_pct = battery.percentage

        if ve_pct <= 0:
            return

        laps = current.session.completed_laps
        if laps < 1:
            return

        # Detect recharge
        if self._last_ve_pct > 0 and ve_pct > self._last_ve_pct + 5:
            self._announced_low = False
            self._announced_critical = False
            self.play_message(QueuedMessage(
                "battery/recharge_complete", expires=10, priority=6,
                fragments=contents("battery fully recharged"),
            ))

        # Track consumption per lap
        if laps != self._last_lap and self._last_ve_pct > 0:
            delta = self._last_ve_pct - ve_pct
            if delta > 0:
                self._ve_samples.append(delta)
                if len(self._ve_samples) > 10:
                    self._ve_samples.pop(0)

        if len(self._ve_samples) >= _MIN_SAMPLES:
            self._avg_consumption = sum(self._ve_samples) / len(self._ve_samples)

        # Warnings
        if ve_pct <= _LOW_VE_PCT and not self._announced_low:
            self.play_message(QueuedMessage(
                "battery/battery_low", expires=10, priority=10,
                fragments=contents("battery below 25 percent"),
            ))
            self._announced_low = True

        if ve_pct <= _CRITICAL_VE_PCT and not self._announced_critical:
            self.play_message_immediately(QueuedMessage(
                "battery/battery_critical", expires=10, priority=15,
                fragments=contents("battery critical, recharge needed"),
            ))
            self._announced_critical = True

        self._last_ve_pct = ve_pct
        self._last_lap = laps

    def clear_state(self) -> None:
        self._ve_samples.clear()
        self._announced_low = False
        self._announced_critical = False
        self._last_ve_pct = -1.0
        self._last_lap = -1
        self._avg_consumption = 0.0
