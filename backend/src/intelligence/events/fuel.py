"""FuelEvent — Monitor de combustible: consumo/vuelta, ventanas, end of stint."""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents
from src.intelligence.event_flags import event_flags

logger = logging.getLogger("vantare.fuel")

_MIN_SAMPLES_FOR_AVG = 3
_LOW_FUEL_LAPS = 3
_END_OF_STINT_LAPS = 1
_MAX_CONSUMPTION_DELTA = 20.0  # Reject >20L/vuelta (would be pit stop, not consumption)


class FuelEvent(AbstractEvent):
    applicable_session_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_session_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW
    ]
    message_category = "FUEL"
    sequence = 20

    def __init__(self, audio_player=None):
        super().__init__(audio_player=audio_player)
        self._consumption_samples: list = []
        self._announced_low: bool = False
        self._announced_end_of_stint: bool = False
        self._last_fuel: float = -1.0
        self._last_lap: int = -1
        self._avg_consumption: float = 0.0
        self._fuel_ok_after_refuel_announced: bool = False
        self._stint_laps_since_refuel: int = 0

    def trigger_internal(
        self, previous: Optional[GameStateData], current: GameStateData
    ) -> None:
        if current is None:
            return

        # Skip if pitting
        if event_flags.is_pitting_this_lap:
            return

        fuel = current.fuel
        fuel_left = fuel.fuel_left
        laps = current.session.completed_laps

        if laps < 1:
            return
        if fuel_left <= 0:
            self._last_fuel = fuel_left
            self._last_lap = laps
            return

        # Detect refuel
        if self._last_fuel > 0 and fuel_left > self._last_fuel + 0.5:
            self._announced_low = False
            self._announced_end_of_stint = False
            event_flags.fuel_warning_active = False
            if not self._fuel_ok_after_refuel_announced:
                self.play_message(QueuedMessage(
                    "fuel/fuel_ok_after_refuel", expires=10, priority=6,
                    fragments=contents("fuel looks good"),
                ))
                self._fuel_ok_after_refuel_announced = True
            # Reset for next stint after 3 laps without refuel
            self._stint_laps_since_refuel = 0

        # Track laps since refuel — reset flag after 3 laps for next stint
        if laps != self._last_lap and laps > 1:
            self._stint_laps_since_refuel = getattr(self, '_stint_laps_since_refuel', 0) + 1
            if self._stint_laps_since_refuel >= 3 and self._fuel_ok_after_refuel_announced:
                self._fuel_ok_after_refuel_announced = False

        # Calculate consumption per lap
        if laps != self._last_lap and self._last_fuel > 0:
            delta = self._last_fuel - fuel_left
            if 0 < delta <= _MAX_CONSUMPTION_DELTA:
                self._consumption_samples.append(delta)
                if len(self._consumption_samples) > 10:
                    self._consumption_samples.pop(0)

        if len(self._consumption_samples) >= _MIN_SAMPLES_FOR_AVG:
            self._avg_consumption = sum(self._consumption_samples) / len(self._consumption_samples)
        else:
            self._avg_consumption = 0.0

        # Estimate laps left
        if self._avg_consumption > 0:
            laps_left = int(fuel_left / self._avg_consumption)

            # Low fuel warning
            if laps_left <= _LOW_FUEL_LAPS and not self._announced_low:
                self.play_message(QueuedMessage(
                    "fuel/low_fuel_warning", expires=10, priority=10,
                    fragments=contents(f"{laps_left} laps of fuel remaining"),
                ))
                self._announced_low = True
                event_flags.fuel_warning_active = True

            # End of stint
            if laps_left <= _END_OF_STINT_LAPS and not self._announced_end_of_stint:
                self.play_message(QueuedMessage(
                    "fuel/end_of_stint", expires=5, priority=12,
                    fragments=contents("last lap of fuel"),
                ))
                self._announced_end_of_stint = True

        self._last_fuel = fuel_left
        self._last_lap = laps

    def clear_state(self) -> None:
        self._consumption_samples.clear()
        self._announced_low = False
        self._announced_end_of_stint = False
        self._last_fuel = -1.0
        self._last_lap = -1
        self._avg_consumption = 0.0
        self._fuel_ok_after_refuel_announced = False
