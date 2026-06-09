from __future__ import annotations

from abc import ABC, abstractmethod

from .types import CrewChiefFrameContext, CrewChiefMessage


class CrewChiefEventModule(ABC):
    event_name = "abstract"

    def clear_state(self) -> None:
        """Reset module-local state at session boundaries."""

    def is_message_still_valid(self, message: CrewChiefMessage, ctx: CrewChiefFrameContext) -> bool:
        return True

    @abstractmethod
    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        raise NotImplementedError
