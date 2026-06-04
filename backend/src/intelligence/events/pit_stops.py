"""PitStops — State machine completa de pit stops.

PIT_NONE → PIT_REQUEST → PIT_ENTERING → PIT_STOPPED → PIT_EXITING
Detecta limiter, countdown, parada obligatoria, salida.
Cruza flags con Fuel y DamageReporting.
"""

import time
import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase, PitWindow
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents
from src.intelligence.event_flags import event_flags

logger = logging.getLogger("vantare.pit_stops")

C_PIT_ENTRY = "pit_stops/pit_entry"
C_PIT_COUNTDOWN = "pit_stops/countdown"
C_GOGOGO = "pit_stops/go_go_go"
C_MANDATORY_DONE = "pit_stops/mandatory_stop_done"
C_LIMITER = "pit_stops/limiter_active"
C_PIT_WINDOW = "pit_stops/pit_window_open"
C_PIT_REQUESTED = "pit_stops/pit_requested"

LMU_PIT_NONE = 0
LMU_PIT_REQUEST = 1
LMU_PIT_ENTERING = 2
LMU_PIT_STOPPED = 3
LMU_PIT_EXITING = 4


class PitStops(AbstractEvent):
    applicable_session_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_session_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW
    ]
    message_category = "PIT_STOPS"
    sequence = 15

    def __init__(self, audio_player=None):
        super().__init__(audio_player=audio_player)
        self._last_pit_state: int = LMU_PIT_NONE
        self._pit_entry_time: float = 0.0
        self._countdown_announced: bool = False
        self._played_countdown_go: bool = False
        self._last_pit_stop_count: int = -1
        self._limiter_announced: bool = False
        self._pit_window_announced: bool = False
        self._pit_request_announced: bool = False

    def should_suppress(self, gsd: GameStateData) -> bool:
        if super().should_suppress(gsd):
            return True
        if gsd is not None and not self.is_applicable(
            gsd.session.session_type, gsd.session.session_phase
        ):
            return True
        return False

    def trigger_internal(
        self, previous: Optional[GameStateData], current: GameStateData
    ) -> None:
        if current is None:
            return

        pit = current.pit
        pit_state = getattr(pit, "pit_state", LMU_PIT_NONE)
        in_pitlane = pit.in_pitlane

        # Detect pit entry
        if (pit_state == LMU_PIT_ENTERING and
                self._last_pit_state != LMU_PIT_ENTERING):
            event_flags.is_pitting_this_lap = True
            self._pit_entry_time = current.now
            self._countdown_announced = False
            self._played_countdown_go = False
            self.play_message(QueuedMessage(
                C_PIT_ENTRY, expires=5, priority=10,
                fragments=contents("pit entry"),
            ))

        # Speed limiter warning
        speed_limiter = getattr(pit, 'speed_limiter', pit.pit_speed_limit > 0)
        if speed_limiter and not self._limiter_announced:
            self.play_message(QueuedMessage(
                C_LIMITER, expires=5, priority=8,
                fragments=contents("pit speed limiter active"),
            ))
            self._limiter_announced = True
        elif not speed_limiter:
            self._limiter_announced = False

        # Pit request detection
        if pit_state == LMU_PIT_REQUEST and not self._pit_request_announced:
            self.play_message(QueuedMessage(
                C_PIT_REQUESTED, expires=5, priority=8,
                fragments=contents("pit stop requested"),
            ))
            self._pit_request_announced = True
        elif pit_state != LMU_PIT_REQUEST:
            self._pit_request_announced = False

        # Detener en boxes
        if pit_state == LMU_PIT_STOPPED:
            event_flags.is_pitting_this_lap = True
            # Countdown — only if we transitioned through ENTERING
            if (not self._countdown_announced and
                    self._last_pit_state == LMU_PIT_ENTERING):
                self.play_message(QueuedMessage(
                    C_PIT_COUNTDOWN, expires=5, priority=10,
                    fragments=contents("pit countdown"),
                ))
                self._countdown_announced = True

            # Mandatory stop
            num = pit.num_pitstops
            if (self._last_pit_stop_count >= 0 and
                    num > self._last_pit_stop_count):
                event_flags.played_request_pit_on_this_lap = False
                event_flags.waiting_for_mandatory_stop_timer = False
                self.play_message(QueuedMessage(
                    C_MANDATORY_DONE, expires=5, priority=10,
                    fragments=contents("mandatory stop completed"),
                ))

        if pit_state != LMU_PIT_STOPPED:
            self._last_pit_stop_count = pit.num_pitstops

        # Salida de boxes
        if (pit_state == LMU_PIT_EXITING and
                self._last_pit_state == LMU_PIT_STOPPED):
            if not self._played_countdown_go:
                self.play_message_immediately(QueuedMessage(
                    C_GOGOGO, expires=3, priority=15,
                    fragments=contents("go go go"),
                ))
                self._played_countdown_go = True

        # Fuera de pits
        if (pit_state == LMU_PIT_NONE and
                self._last_pit_state > LMU_PIT_NONE):
            if not in_pitlane:
                event_flags.is_pitting_this_lap = False
                self._countdown_announced = False
                self._played_countdown_go = False

        # Pit window detection — uses track_definition.FUEL_WINDOW_LENGTH
        if (pit_state == LMU_PIT_NONE and not in_pitlane and
                current.session.track_definition):
            laps = current.session.completed_laps
            td = current.session.track_definition
            from src.services.track_definition import FUEL_WINDOW_LENGTH
            window_start = FUEL_WINDOW_LENGTH.get(td.track_length_class, 3)
            window_end = window_start + 5
            if window_start <= laps <= window_end and not self._pit_window_announced:
                self.play_message(QueuedMessage(
                    C_PIT_WINDOW, expires=10, priority=6,
                    fragments=contents("pit window open"),
                ))
                self._pit_window_announced = True

        self._last_pit_state = pit_state

    def clear_state(self) -> None:
        self._last_pit_state = LMU_PIT_NONE
        self._pit_entry_time = 0.0
        self._countdown_announced = False
        self._played_countdown_go = False
        self._last_pit_stop_count = -1
        self._limiter_announced = False
        self._pit_window_announced = False
        self._pit_request_announced = False
