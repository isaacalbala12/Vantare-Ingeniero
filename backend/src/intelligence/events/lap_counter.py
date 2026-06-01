"""LapCounter: detecta vueltas nuevas y de warmup, anuncia número de vuelta.

Eventos que dispara:
- lap_completed: cada vez que se completa una vuelta
- first_lap_after_pit: primera vuelta después de parar en boxes
- warmup_lap: vuelta de warmup en formación
"""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.intelligence.event_flags import event_flags
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents
from src.services.utilities import random_int

logger = logging.getLogger("vantare.events.lap")

F_LAP = "lap/new_lap"
F_FIRST_LAP_AFTER_PIT = "lap/first_lap_after_pit"
F_WARMUP = "lap/warmup_lap"


class LapCounter(AbstractEvent):
    applicable_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW, SessionPhase.CHECKERED
    ]
    category = "ALL"
    sequence = 30

    def __init__(self, ap=None) -> None:
        super().__init__(ap)
        self._prev_lap: int = 0
        self._prev_sector: int = 1
        self._was_pitting: bool = False
        self._played_first_lap_after_pit: bool = False

    def clear_state(self) -> None:
        self._prev_lap = 0
        self._prev_sector = 1
        self._was_pitting = False
        self._played_first_lap_after_pit = False
        event_flags.last_lap_was_pit_lap = False

    def trigger_internal(
        self, prev: Optional[GameStateData], curr: GameStateData
    ) -> None:
        if self.should_suppress(curr):
            self._prev_lap = curr.session.completed_laps
            return

        current_lap = curr.session.completed_laps
        in_pits = curr.pit.in_pitlane

        # Detectar pit in/out
        if in_pits and not self._was_pitting:
            # Entrando a pits
            pass
        elif not in_pits and self._was_pitting:
            # Saliendo de pits
            self._played_first_lap_after_pit = False
        self._was_pitting = in_pits

        # Detección de vuelta nueva
        if self._prev_lap > 0 and current_lap > self._prev_lap:
            new_lap = current_lap

            # Si la vuelta anterior fue de pit, marcar
            if self._prev_lap == event_flags.last_lap_was_pit_lap:
                pass

            event_flags.last_lap_was_pit_lap = (
                self._prev_lap if not in_pits else False
            )

            # Warmup lap: primera vuelta tras salir de pits
            if not self._played_first_lap_after_pit and prev is not None and prev.pit.in_pitlane:
                self._played_first_lap_after_pit = True
                self.play(QueuedMessage(
                    F_WARMUP, expires=5, priority=5,
                    fragments=contents("warmup lap"),
                ))

            # Anunciar número de vuelta (cooldown: cada vuelta)
            self.play(QueuedMessage(
                F_LAP, expires=5, priority=5,
                fragments=contents("lap", new_lap),
            ))

        self._prev_lap = current_lap
        self._prev_sector = curr.session.sector_number
