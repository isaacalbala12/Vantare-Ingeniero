"""MulticlassWarnings — advierte de tráfico más lento/rápido en multiclase.

Eventos que dispara:
- multiclass/traffic_ahead: cuando un coche más lento está delante (≤3s)
- multiclass/car_catching: cuando un coche más rápido se acerca por detrás (≤3s)
"""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents

logger = logging.getLogger("vantare.events.multiclass")

_TRAFFIC_DELTA_MAX = 3.0       # Segundos para considerar tráfico cercano
_SLOWER_FACTOR = 0.9           # Fracción de velocidad para detectar lento
_FASTER_FACTOR = 1.1           # Fracción de velocidad para detectar rápido


class MulticlassWarnings(AbstractEvent):
    applicable_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE,
    ]
    applicable_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW,
    ]
    category = "ALL"
    sequence = 6

    def __init__(self, audio_player=None) -> None:
        super().__init__(audio_player=audio_player)

    def trigger_internal(
        self, prev: Optional[GameStateData], curr: GameStateData
    ) -> None:
        if curr is None or not curr.opponents:
            return

        player_speed = curr.motion.car_speed
        if player_speed <= 0:
            return

        for name, opp in curr.opponents.items():
            if not opp.active:
                continue
            delta = abs(opp.delta)
            if delta == 0 or delta > _TRAFFIC_DELTA_MAX:
                continue

            if opp.speed < player_speed * _SLOWER_FACTOR:
                # Slower car ahead
                self.play_imm(QueuedMessage(
                    "multiclass/traffic_ahead", expires=5, priority=15,
                    fragments=contents("traffic ahead"),
                ))
            elif opp.speed > player_speed * _FASTER_FACTOR:
                # Faster car catching from behind
                self.play_imm(QueuedMessage(
                    "multiclass/car_catching", expires=5, priority=15,
                    fragments=contents("faster car catching"),
                ))

    def clear_state(self) -> None:
        pass
