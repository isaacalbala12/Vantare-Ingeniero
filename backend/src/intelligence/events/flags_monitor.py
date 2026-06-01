"""FlagsMonitor: detecta cambios de fase (green/FCY/checkered) y dispara mensajes.

Eventos que dispara:
- fcy_deployed: cuando se entra en Full Course Yellow
- fcy_ending: cuando el FCY está terminando (LAST_LAP_NEXT)
- fcy_ended: cuando se vuelve a green tras FCY
- chequered: cuando se recibe la bandera a cuadros
- session_finished: cuando la sesión termina
"""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.intelligence.event_flags import event_flags
from src.models.enums import SessionType, SessionPhase, FullCourseYellowPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents
from src.services.utilities import random_int

logger = logging.getLogger("vantare.events.flags")

F_FCY_DEPLOYED = "fcy/fcy_deployed"
F_FCY_ENDING = "fcy/fcy_ending"
F_FCY_ENDED = "fcy/fcy_ended"
F_CHEQUERED = "session/chequered"
F_FINISHED = "session/finished"


class FlagsMonitor(AbstractEvent):
    applicable_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW,
        SessionPhase.CHECKERED, SessionPhase.FINISHED,
        SessionPhase.FORMATION, SessionPhase.COUNTDOWN,
    ]
    category = "ALL"
    sequence = 5  # Antes que todo lo demás

    def __init__(self, ap=None) -> None:
        super().__init__(ap)
        self._prev_phase: Optional[SessionPhase] = None
        self._prev_fcy_phase: Optional[FullCourseYellowPhase] = None
        self._laps_in_fcy: int = 0

    def clear_state(self) -> None:
        self._prev_phase = None
        self._prev_fcy_phase = None
        self._laps_in_fcy = 0

    def trigger_internal(
        self, prev: Optional[GameStateData], curr: GameStateData
    ) -> None:
        if self.should_suppress(curr):
            self._prev_phase = curr.session.session_phase
            return

        current_phase = curr.session.session_phase
        current_fcy_phase = curr.flag.fcy_phase
        now = curr.now

        # Detección de FCY (de Green a FullCourseYellow)
        if (
            self._prev_phase == SessionPhase.GREEN
            and current_phase == SessionPhase.FULL_COURSE_YELLOW
        ):
            self._laps_in_fcy = 0
            self.play(QueuedMessage(
                F_FCY_DEPLOYED, expires=10, priority=10,
                fragments=contents("safety car deployed"),
            ))

        # FCY terminando (LAST_LAP_NEXT)
        if (
            self._prev_fcy_phase is not None
            and current_fcy_phase == FullCourseYellowPhase.LAST_LAP_NEXT
            and self._prev_fcy_phase != FullCourseYellowPhase.LAST_LAP_NEXT
        ):
            self.play(QueuedMessage(
                F_FCY_ENDING, expires=10, priority=10,
                fragments=contents("safety car ending this lap"),
            ))

        # FCY terminó (vuelta a green)
        if (
            self._prev_phase == SessionPhase.FULL_COURSE_YELLOW
            and current_phase == SessionPhase.GREEN
        ):
            self._laps_in_fcy = 0
            self.play(QueuedMessage(
                F_FCY_ENDED, expires=10, priority=10,
                fragments=contents("green flag, go go go"),
            ))

        # Chequered
        if (
            self._prev_phase != SessionPhase.CHECKERED
            and current_phase == SessionPhase.CHECKERED
        ):
            self.play(QueuedMessage(
                F_CHEQUERED, expires=10, priority=10,
                fragments=contents("chequered flag"),
            ))

        # Finished
        if (
            self._prev_phase != SessionPhase.FINISHED
            and current_phase == SessionPhase.FINISHED
        ):
            self.play(QueuedMessage(
                F_FINISHED, expires=10, priority=10,
                fragments=contents("session finished"),
            ))

        # Actualizar flags compartidos
        if current_phase == SessionPhase.FULL_COURSE_YELLOW:
            event_flags.green_for_n_laps = 0
        elif current_phase == SessionPhase.GREEN:
            if self._prev_phase != SessionPhase.GREEN:
                # Vuelta a green: reset
                event_flags.green_for_n_laps = 0
            else:
                event_flags.green_for_n_laps += 1

        self._prev_phase = current_phase
        self._prev_fcy_phase = current_fcy_phase
