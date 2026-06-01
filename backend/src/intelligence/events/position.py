"""PositionEvent: anuncia cambios de posición y mensajes relacionados.

Eventos que dispara:
- new_leader: cuando el jugador se pone líder
- lost_lead: cuando el jugador pierde el liderato
- position_gained: cuando se adelanta a alguien
- position_lost: cuando te adelantan
- consistently_last: si vas último varias vueltas
"""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.intelligence.event_flags import event_flags
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents
from src.services.utilities import random_int

logger = logging.getLogger("vantare.events.position")

F_LEADING = "position/leading"
F_NEW_LEADER = "position/new_leader"
F_LOST_LEAD = "position/lost_lead"
F_OVERTAKE = "position/overtaking"
F_BEING_OVERTAKEN = "position/being_overtaken"
F_LAST = "position/last"
F_CONSISTENTLY_LAST = "position/consistently_last"
F_POLE = "position/pole"


class PositionEvent(AbstractEvent):
    applicable_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW, SessionPhase.CHECKERED
    ]
    category = "ALL"
    sequence = 20

    def __init__(self, ap=None) -> None:
        super().__init__(ap)
        self.pos: int = 0
        self.prev_pos: int = 0
        self.start_pos: Optional[int] = None
        self.was_leader: bool = False
        self.is_leader: bool = False
        self.laps_last: int = 0
        self.last_overtake_time: float = 0.0
        self.last_overtaken_time: float = 0.0
        self.last_class_size: int = 0
        self._bounce: float = 1.0
        self._pending: dict = {}

    def clear_state(self) -> None:
        self.pos = 0
        self.prev_pos = 0
        self.start_pos = None
        self.was_leader = False
        self.is_leader = False
        self.laps_last = 0
        self.last_overtake_time = 0.0
        self.last_overtaken_time = 0.0
        self.last_class_size = 0
        self._pending.clear()
        # old_pos se reinicia implícitamente (es variable local)

    def _bounce_pos(self, key: str, old: int, new: int, now: float) -> int:
        """Anti-bounce: solo acepta el cambio tras 1s estable.

        Si now <= 0 (modo test sin tiempo real), acepta el cambio inmediatamente.
        """
        if old == new:
            self._pending.pop(key, None)
            return old
        # Modo test / sin tiempo real: aceptar inmediatamente
        if now <= 0:
            self._pending.pop(key, None)
            return new
        p = self._pending.get(key)
        if p and p["new"] == new:
            if now >= p["settle"]:
                self._pending.pop(key, None)
                return new
            return old
        self._pending[key] = {"new": new, "settle": now + self._bounce}
        return old

    def trigger_internal(
        self, prev: Optional[GameStateData], curr: GameStateData
    ) -> None:
        if self.should_suppress(curr):
            self.prev_pos = curr.session.class_position
            return

        if event_flags.on_formation:
            return

        new_pos = curr.session.class_position
        now = curr.now
        old_pos = self.prev_pos  # Posición estable del tick anterior

        # Anti-bounce: el bounce es entre el "pos aceptado" actual y el nuevo
        self.pos = self._bounce_pos("position", self.prev_pos, new_pos, now)

        # Detección de liderato
        self.was_leader = self.is_leader
        num_cars = len(curr.opponents) + 1
        self.is_leader = (new_pos == 1 and num_cars > 1)

        # En qualify, si estamos en P1, es "pole" no "new_leader"
        # IMPORTANTE: este chequeo debe ir ANTES de guardar start_pos
        if (
            curr.session.session_type == SessionType.QUALIFY
            and new_pos == 1
            and self.start_pos is None
        ):
            self.start_pos = 1
            self.play(QueuedMessage(
                F_POLE, expires=10, priority=10,
                fragments=contents("pole position"),
            ))
        else:
            # Primera vuelta en RACE/PRACTICE: guardar posición de salida
            if self.start_pos is None and new_pos > 0:
                self.start_pos = new_pos

            # Detección de nuevo líder/perdida de liderato
            if not self.was_leader and self.is_leader:
                self.play(QueuedMessage(
                    F_NEW_LEADER, expires=10, priority=10,
                    fragments=contents("you are now leading"),
                ))
                self.play(QueuedMessage(
                    F_LEADING, expires=10, priority=5,
                    fragments=contents("leading"),
                ))
            elif self.was_leader and not self.is_leader and new_pos > 1:
                # Cooldown 30s para no repetir (desactivado en modo test)
                if now <= 0 or now - self.last_overtaken_time > 30:
                    self.last_overtaken_time = now
                    self.play(QueuedMessage(
                        F_LOST_LEAD, expires=10, priority=10,
                        fragments=contents("lost position, now p", new_pos),
                    ))

        # Cooldown desactivado en modo test (now <= 0)
        cooldown_ok = (now <= 0) or (now - self.last_overtake_time > 5)
        cooldown_ok2 = (now <= 0) or (now - self.last_overtaken_time > 5)

        # Detección de overtake (pos mejora)
        if self.pos < old_pos and old_pos > 0 and self.pos > 0 and cooldown_ok:
            self.last_overtake_time = now
            self.play(QueuedMessage(
                F_OVERTAKE, expires=5, priority=8,
                fragments=contents("overtaking, now p", self.pos),
            ))

        # Detección de ser adelantado (pos empeora)
        elif self.pos > old_pos and old_pos > 0 and self.pos > 0 and cooldown_ok2:
            self.last_overtaken_time = now
            self.play(QueuedMessage(
                F_BEING_OVERTAKEN, expires=5, priority=8,
                fragments=contents("being overtaken, now p", self.pos),
            ))

        # Detección de último (consistente)
        if (
            self.pos == num_cars
            and num_cars > 1
        ):
            self.laps_last += 1
            if self.laps_last == 3:
                self.play(QueuedMessage(
                    F_CONSISTENTLY_LAST, expires=10, priority=5,
                    fragments=contents("running last for 3 laps"),
                ))
        else:
            self.laps_last = 0

        self.prev_pos = self.pos
        self.last_class_size = num_cars
