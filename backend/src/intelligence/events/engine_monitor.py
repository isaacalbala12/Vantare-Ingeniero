"""EngineMonitor — Temperaturas motor (agua/aceite), stall, RPM limit."""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents
from src.intelligence.event_flags import event_flags

logger = logging.getLogger("vantare.engine_monitor")

_MIN_SAMPLES = 10
_DEFAULT_MAX_WATER = 110.0
_DEFAULT_MAX_OIL = 130.0
_RPM_LIMIT_FACTOR = 0.95
_MIN_SPEED_FOR_STALL = 2.0

# Per-class thresholds (fallback if car_class_data lookup fails)
_CLASS_WATER_THRESHOLDS = {
    "GT3": 110.0, "HYPER_CAR": 105.0, "LMGT3": 110.0,
    "LMP2": 108.0, "LMP1": 105.0, "UNKNOWN_RACE": 110.0,
}
_CLASS_OIL_THRESHOLDS = {
    "GT3": 130.0, "HYPER_CAR": 125.0, "LMGT3": 130.0,
    "LMP2": 128.0, "LMP1": 125.0, "UNKNOWN_RACE": 130.0,
}


class EngineMonitor(AbstractEvent):
    applicable_session_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_session_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW
    ]
    message_category = "ENGINE"
    sequence = 40

    def __init__(self, audio_player=None):
        super().__init__(audio_player=audio_player)
        self._water_samples: list = []
        self._oil_samples: list = []
        self._announced_water_overheat: bool = False
        self._announced_oil_overheat: bool = False
        self._announced_stalled: bool = False
        self._stall_timer: float = 0.0
        self._announced_rpm_limit: bool = False

    def trigger_internal(
        self, previous: Optional[GameStateData], current: GameStateData
    ) -> None:
        if current is None:
            return

        engine = current.engine
        water = engine.water_temp
        oil = engine.oil_temp
        rpm = engine.rpm
        gear = engine.gear
        max_rpm = engine.max_rpm
        speed = current.motion.car_speed
        overheating = engine.overheating

        # Collect samples
        self._water_samples.append(water)
        self._oil_samples.append(oil)
        if len(self._water_samples) > 30:
            self._water_samples.pop(0)
        if len(self._oil_samples) > 30:
            self._oil_samples.pop(0)

        # Overheating icon — warns immediately, regardless of sample count
        if overheating:
            if not self._announced_water_overheat:
                self.play_message_immediately(QueuedMessage(
                    "engine_monitor/engine_overheating", expires=10, priority=15,
                    fragments=contents("engine overheating"),
                ))
                self._announced_water_overheat = True

        # Check if we have minimum samples
        if len(self._water_samples) < _MIN_SAMPLES:
            return

        # Rolling average
        avg_water = sum(self._water_samples) / len(self._water_samples)
        avg_oil = sum(self._oil_samples) / len(self._oil_samples)

        # Get class-specific thresholds
        cls = current.car_class.upper() if current.car_class else "UNKNOWN_RACE"
        max_water = _CLASS_WATER_THRESHOLDS.get(cls, _DEFAULT_MAX_WATER)
        max_oil = _CLASS_OIL_THRESHOLDS.get(cls, _DEFAULT_MAX_OIL)

        # Water temp
        if avg_water >= max_water and not self._announced_water_overheat:
            self.play_message(QueuedMessage(
                "engine_monitor/engine_overheating", expires=10, priority=12,
                fragments=contents(f"engine overheating, water at {avg_water:.0f} degrees"),
            ))
            self._announced_water_overheat = True

        # Oil temp
        if avg_oil >= max_oil and not self._announced_oil_overheat:
            self.play_message(QueuedMessage(
                "engine_monitor/oil_overheating", expires=10, priority=12,
                fragments=contents("oil temperature critical"),
            ))
            self._announced_oil_overheat = True

        # Reset overheat flags when temps go back to normal
        if avg_water < max_water - 5:
            self._announced_water_overheat = False
        if avg_oil < max_oil - 5:
            self._announced_oil_overheat = False

        # RPM limit warning
        if max_rpm > 0 and rpm >= max_rpm * _RPM_LIMIT_FACTOR:
            if not self._announced_rpm_limit:
                self.play_message(QueuedMessage(
                    "engine_monitor/rpm_limit", expires=5, priority=8,
                    fragments=contents("watch your revs"),
                ))
                self._announced_rpm_limit = True
        else:
            self._announced_rpm_limit = False

        # Engine stall
        if rpm <= 0 and gear > 0 and speed > _MIN_SPEED_FOR_STALL:
            if not self._announced_stalled:
                self._stall_timer = current.now
                self.play_message_immediately(QueuedMessage(
                    "engine_monitor/engine_stalled", expires=5, priority=15,
                    fragments=contents("engine stalled"),
                ))
                self._announced_stalled = True
        else:
            self._announced_stalled = False

    def clear_state(self) -> None:
        self._water_samples.clear()
        self._oil_samples.clear()
        self._announced_water_overheat = False
        self._announced_oil_overheat = False
        self._announced_stalled = False
        self._stall_timer = 0.0
        self._announced_rpm_limit = False
