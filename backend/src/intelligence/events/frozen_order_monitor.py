"""FrozenOrderMonitor — Detecta fases de Safety Car y orden congelado.

Lee FrozenOrderData y SessionPhase. Usa FCY para SC deployed, NONE para SC ended.
"""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase, FrozenOrderPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents
from src.intelligence.event_flags import event_flags

logger = logging.getLogger("vantare.frozen_order")


class FrozenOrderMonitor(AbstractEvent):
    applicable_session_types = [SessionType.RACE]
    applicable_session_phases = [
        SessionPhase.FORMATION, SessionPhase.GREEN,
        SessionPhase.FULL_COURSE_YELLOW,
    ]
    message_category = "FROZEN_ORDER"
    sequence = 7

    def __init__(self, audio_player=None):
        super().__init__(audio_player=audio_player)
        self._last_fo_phase = FrozenOrderPhase.NONE
        self._sc_deployed_announced = False
        self._sc_ending_announced = False

    def trigger_internal(
        self, previous: Optional[GameStateData], current: GameStateData
    ) -> None:
        if current is None:
            return

        fo = current.frozen_order
        if fo is None:
            return

        fo_phase = fo.phase

        # SC deployed: entering FCY frozen order
        if (fo_phase == FrozenOrderPhase.FCY and
                not self._sc_deployed_announced and
                self._last_fo_phase != FrozenOrderPhase.FCY):
            if not event_flags.on_manual_formation_lap:
                self.play_message_immediately(QueuedMessage(
                    "frozen_order/sc_deployed", expires=10, priority=15,
                    fragments=contents("safety car deployed"),
                ))
            self._sc_deployed_announced = True
            self._sc_ending_announced = False

        # SC ending: transitioning from FCY back to NONE
        if (fo_phase == FrozenOrderPhase.NONE and
                self._last_fo_phase == FrozenOrderPhase.FCY and
                not self._sc_ending_announced):
            self.play_message(QueuedMessage(
                "frozen_order/sc_ending", expires=10, priority=12,
                fragments=contents("safety car ending"),
            ))
            self._sc_ending_announced = True
            self._sc_deployed_announced = False

        # SC ending via GREEN transition (not just NONE)
        if (fo_phase == FrozenOrderPhase.NONE and
                current.session.session_phase == SessionPhase.GREEN and
                self._last_fo_phase == FrozenOrderPhase.FCY and
                not self._sc_ending_announced):
            self.play_message(QueuedMessage(
                "frozen_order/sc_ending", expires=10, priority=12,
                fragments=contents("safety car ending"),
            ))
            self._sc_ending_announced = True
            self._sc_deployed_announced = False

        # Formation → ROLLING: rolling start
        if (fo_phase == FrozenOrderPhase.ROLLING and
                self._last_fo_phase == FrozenOrderPhase.ROLLING):
            pass  # Already rolling, no new message

        # Reset flags when stable at NONE
        if fo_phase == FrozenOrderPhase.NONE and self._last_fo_phase == FrozenOrderPhase.NONE:
            self._sc_deployed_announced = False
            self._sc_ending_announced = False

        self._last_fo_phase = fo_phase

    def clear_state(self) -> None:
        self._last_fo_phase = FrozenOrderPhase.NONE
        self._sc_deployed_announced = False
        self._sc_ending_announced = False
