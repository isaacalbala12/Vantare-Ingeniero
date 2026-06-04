"""ConditionsMonitor — Detecta cambios de clima durante la carrera.

Lee temperatura ambiente, temperatura de pista y lluvia del REST API.
Relevante para PitStops (¿pista mojada? → neumáticos wet) y TyreMonitor (temps).
"""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, MessageFragment, contents

logger = logging.getLogger("vantare.conditions_monitor")

_DRY_THRESHOLD = 0.15
_RAIN_THRESHOLD = 0.4
_TEMP_CHANGE_THRESHOLD = 5.0
_MIN_MESSAGE_INTERVAL = 30.0


class ConditionsMonitor(AbstractEvent):
    applicable_session_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_session_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW
    ]
    message_category = "CONDITIONS"
    sequence = 5

    def __init__(self, audio_player=None):
        super().__init__(audio_player=audio_player)
        self._was_raining = False
        self._last_rain_intensity = 0.0
        self._announced_track_temp = -999.0
        self._last_temp_msg_time = 0.0
        self._last_rain_msg_time = 0.0

    def trigger_internal(
        self, previous: Optional[GameStateData], current: GameStateData
    ) -> None:
        if current is None or current.weather is None:
            return

        now = current.now

        # Rain detection
        rain = current.weather.rain_intensity

        is_raining = rain >= _RAIN_THRESHOLD
        is_dry = rain <= _DRY_THRESHOLD

        if is_raining and not self._was_raining:
            if now - self._last_rain_msg_time >= _MIN_MESSAGE_INTERVAL:
                self.play_message(QueuedMessage(
                    "conditions/rain_starting", expires=10, priority=10,
                    fragments=contents("rain starting, be careful"),
                ))
                self._last_rain_msg_time = now
            self._was_raining = True

        elif is_dry and self._was_raining:
            if now - self._last_rain_msg_time >= _MIN_MESSAGE_INTERVAL:
                self.play_message(QueuedMessage(
                    "conditions/rain_stopping", expires=10, priority=8,
                    fragments=contents("track is drying"),
                ))
                self._last_rain_msg_time = now
            self._was_raining = False

        self._last_rain_intensity = rain

        # Track temp change detection
        track_temp = current.weather.track_temp
        if track_temp <= -998:
            return

        if self._announced_track_temp < -100:
            self._announced_track_temp = track_temp
            return

        delta = track_temp - self._announced_track_temp
        if abs(delta) >= _TEMP_CHANGE_THRESHOLD:
            if now - self._last_temp_msg_time >= _MIN_MESSAGE_INTERVAL:
                direction = "rising" if delta > 0 else "dropping"
                self.play_message(QueuedMessage(
                    f"conditions/track_temp_{direction}", expires=10, priority=6,
                    fragments=contents(f"track temperature {direction}"),
                ))
                self._last_temp_msg_time = now
            self._announced_track_temp = track_temp

    def clear_state(self) -> None:
        self._was_raining = False
        self._last_rain_intensity = 0.0
        self._announced_track_temp = -999.0
        self._last_temp_msg_time = 0.0
        self._last_rain_msg_time = 0.0
