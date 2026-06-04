"""Base class para todos los eventos deterministas del CrewChief.

Cada evento hereda de AbstractEvent y sigue este contrato:
- applicable_types: en qué tipos de sesión se ejecuta
- applicable_phases: en qué fases se ejecuta
- category: categoría de mensajes (para filtrar por clase de coche)
- sequence: orden de ejecución dentro del EventEngine
- trigger_internal(prev, curr): lógica principal
- clear_state(): reset de todos los flags
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents, Pause
from src.intelligence.event_flags import event_flags

logger = logging.getLogger("vantare.events")


class AbstractEvent(ABC):
    applicable_types: List[SessionType] = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_phases: List[SessionPhase] = [
        SessionPhase.GREEN, SessionPhase.COUNTDOWN
    ]
    category: str = "ALL"
    sequence: int = 100

    def __init__(self, ap: Any = None, audio_player: Any = None) -> None:
        # Normalize: if only audio_player given, mirror to ap so play() works
        if ap is None and audio_player is not None:
            ap = audio_player
        self.ap = ap
        self.audio_player = audio_player
        self._failed_count: int = 0
        self._psi: bool = False  # per-session-init

    @abstractmethod
    def trigger_internal(
        self, prev: Optional[GameStateData], curr: GameStateData
    ) -> None:
        pass

    @abstractmethod
    def clear_state(self) -> None:
        pass

    def applicable(self, t: SessionType, p: SessionPhase) -> bool:
        return t in self.applicable_types and p in self.applicable_phases

    def should_suppress(self, g: GameStateData) -> bool:
        if event_flags.on_manual_formation_lap:
            return True
        if not self._enabled(g):
            return True
        return False

    def _enabled(self, g: GameStateData) -> bool:
        from src.config.global_behaviour import global_settings
        return global_settings.message_type_enabled(self.category)

    def is_valid(
        self, sub: str, cur: GameStateData, vd: Optional[Dict] = None
    ) -> bool:
        return cur is not None and self.applicable(
            cur.session.session_type, cur.session.session_phase
        )

    def respond(self, vm: str) -> None:
        """Override para soportar comandos de voz."""
        pass

    @staticmethod
    def C(*o) -> List:
        return contents(*o)

    @staticmethod
    def P(ms: int):
        return Pause(ms)

    def play(self, m) -> None:
        if m is None or not hasattr(m, "can_play"):
            return
        if not m.can_play:
            return
        if self.ap is None:
            return
        if hasattr(self.ap, "play") and callable(self.ap.play):
            try:
                self.ap.play(m)
            except Exception as e:
                name = getattr(m, "name", "<unknown>")
                logger.error(f"play() failed for {name}: {e}")

    def play_imm(self, m) -> None:
        if m is None or not hasattr(m, "can_play"):
            return
        if not m.can_play:
            return
        if self.ap is None:
            return
        if hasattr(self.ap, "play_imm") and callable(self.ap.play_imm):
            try:
                self.ap.play_imm(m)
            except Exception as e:
                name = getattr(m, "name", "<unknown>")
                logger.error(f"play_imm() failed for {name}: {e}")

    # Aliases for test compatibility (pre-existing tests call these directly)
    play_message = play
    play_message_immediately = play_imm
    is_applicable = applicable


class FakeAudioPlayer:
    """Mock AudioPlayer para tests. Mantiene listas de mensajes."""

    def __init__(self) -> None:
        self.msgs: List[QueuedMessage] = []
        self.imms: List[QueuedMessage] = []
        self.spotter_calls: List[str] = []
        self.paused_for: float = 0.0

    def play(self, m: QueuedMessage, **kw) -> None:
        self.msgs.append(m)

    def play_imm(self, m: QueuedMessage, **kw) -> None:
        self.imms.append(m)

    def play_spotter_message(self, p: str, keep_channel: bool = True) -> None:
        self.spotter_calls.append(p)

    def pause_q(self, s: float) -> None:
        self.paused_for = s

    def unpause_q(self) -> None:
        self.paused_for = 0.0

    def clear(self) -> None:
        self.msgs.clear()
        self.imms.clear()
        self.spotter_calls.clear()

    @property
    def messages(self) -> List[QueuedMessage]:
        return self.msgs

    @property
    def immediate_messages(self) -> List[QueuedMessage]:
        return self.imms

    play_message = play
    play_message_immediately = play_imm
