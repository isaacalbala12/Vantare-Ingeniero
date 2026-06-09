from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .base import CrewChiefEventModule
from .session_delay import should_delay_non_critical_message
from .types import CrewChiefFrameContext, CrewChiefMessage


class CrewChiefEventSuite:
    def __init__(
        self,
        modules: Iterable[CrewChiefEventModule] | None = None,
        engine: Any = None,
    ) -> None:
        self.modules = list(modules or [])
        self.engine = engine

    def clear_state(self) -> None:
        for module in self.modules:
            module.clear_state()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        messages: list[CrewChiefMessage] = []
        for module in self.modules:
            for message in module.evaluate(ctx):
                if should_delay_non_critical_message(
                    session=ctx.session,
                    now_monotonic=ctx.now_monotonic,
                    message=message,
                ):
                    continue
                messages.append(message)
        return messages
