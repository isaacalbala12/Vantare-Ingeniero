"""SessionMonitor: detecta transiciones de tipo de sesión y formation laps.

Eventos que dispara:
- formation_start: cuando entramos en fase FORMATION
- formation_end: cuando salimos de FORMATION a GREEN
- pre_session_warmup: vuelta de warmup
"""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.intelligence.event_flags import event_flags
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents

logger = logging.getLogger("vantare.events.session")

F_FORMATION_START = "session/formation_start"
F_FORMATION_END = "session/formation_end"


class SessionMonitor(AbstractEvent):
    applicable_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_phases = [
        SessionPhase.GREEN, SessionPhase.FORMATION,
        SessionPhase.COUNTDOWN, SessionPhase.GRIDWALK,
        SessionPhase.GARAGE, SessionPhase.FULL_COURSE_YELLOW,
        SessionPhase.CHECKERED, SessionPhase.FINISHED,
    ]
    category = "ALL"
    sequence = 10

    def __init__(self, ap=None) -> None:
        super().__init__(ap)
        self._prev_type: Optional[SessionType] = None
        self._prev_phase: Optional[SessionPhase] = None

    def clear_state(self) -> None:
        self._prev_type = None
        self._prev_phase = None
        event_flags.on_formation = False

    def trigger_internal(
        self, prev: Optional[GameStateData], curr: GameStateData
    ) -> None:
        if curr is None:
            return
        if self.should_suppress(curr):
            self._prev_type = curr.session.session_type
            self._prev_phase = curr.session.session_phase
            return

        st = curr.session.session_type
        sp = curr.session.session_phase

        # Detección de inicio de formación.
        # Cubrimos dos casos:
        # 1. Transición desde otra fase -> FORMATION
        # 2. Primer tick y ya estamos en FORMATION (prev=None, sp=FORMATION)
        is_first_tick = self._prev_phase is None
        in_formation_now = sp == SessionPhase.FORMATION
        was_in_formation = self._prev_phase == SessionPhase.FORMATION

        if in_formation_now and not was_in_formation:
            event_flags.on_formation = True
            self.play(QueuedMessage(
                F_FORMATION_START, expires=10, priority=8,
                fragments=contents("formation lap starting"),
            ))

        # Detección de fin de formación
        if (
            self._prev_phase == SessionPhase.FORMATION
            and sp != SessionPhase.FORMATION
        ):
            event_flags.on_formation = False
            if sp == SessionPhase.GREEN:
                self.play(QueuedMessage(
                    F_FORMATION_END, expires=10, priority=8,
                    fragments=contents("go go go, race start"),
                ))

        self._prev_type = st
        self._prev_phase = sp
