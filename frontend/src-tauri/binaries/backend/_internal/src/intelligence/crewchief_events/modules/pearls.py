from __future__ import annotations

from src.intelligence.crewchief_events.lap_edge import lap_completed
from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.pearls_of_wisdom import PearlType, PearlsService

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

FAST_LAP_TOLERANCE_S = 0.05
STANDARD_LAP_INTERVAL = 12


class PearlsEvent(CrewChiefEventModule):
    event_name = "pearls"

    def __init__(self) -> None:
        self._pearls = PearlsService()
        self._last_standing: int | None = None
        self._worst_position: int | None = None
        self._comeback_emitted = False
        self._last_standard_lap = 0

    def clear_state(self) -> None:
        self._pearls.reset_race()
        self._last_standing = None
        self._worst_position = None
        self._comeback_emitted = False
        self._last_standard_lap = 0

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_pearl_messages", True):
            return []

        messages: list[CrewChiefMessage] = []
        sweary = bool(ctx.session.get("sweary_messages"))
        level = str(ctx.session.get("verbosity_level") or "normal").lower()
        pearl_freq = float(ctx.session.get("pearl_frequency") if ctx.session.get("pearl_frequency") is not None else 0.5)
        max_pearls = 4 if level == "detailed" else 2
        if pearl_freq <= 0.0:
            return []

        pos_raw = ctx.current.get("standing_position")
        if pos_raw is not None:
            pos = int(pos_raw)
            if self._worst_position is None or pos > self._worst_position:
                self._worst_position = pos
            if self._last_standing is not None and pos < self._last_standing:
                if msg := self._make_pearl(PearlType.OVERTAKE, sweary, max_pearls, pearl_freq):
                    messages.append(msg)
            if (
                not self._comeback_emitted
                and self._worst_position is not None
                and pos < self._worst_position - 1
            ):
                self._comeback_emitted = True
                if msg := self._make_pearl(PearlType.COMEBACK, sweary, max_pearls, pearl_freq):
                    messages.append(msg)
            self._last_standing = pos

        if ctx.previous and lap_completed(ctx.previous, ctx.current):
            prev = float(ctx.current.get("lap_time_previous") or 0)
            best = float(ctx.current.get("lap_time_best") or 0)
            if prev > 0 and best > 0 and abs(prev - best) < FAST_LAP_TOLERANCE_S:
                if msg := self._make_pearl(PearlType.FAST_LAP, sweary, max_pearls, pearl_freq):
                    messages.append(msg)

            lap = int(ctx.current.get("lap_number") or 0)
            if level == "detailed" and lap > 0 and lap % STANDARD_LAP_INTERVAL == 0 and lap != self._last_standard_lap:
                self._last_standard_lap = lap
                if msg := self._make_pearl(PearlType.STANDARD, sweary, max_pearls, pearl_freq):
                    messages.append(msg)

        return messages[:1]

    def _make_pearl(
        self,
        pearl_type: PearlType,
        sweary: bool,
        max_pearls: int,
        pearl_frequency: float,
        *,
        roll: float | None = None,
    ) -> CrewChiefMessage | None:
        text = self._pearls.on_event(
            pearl_type,
            sweary=sweary,
            max_per_race=max_pearls,
            pearl_frequency=pearl_frequency,
            roll=roll,
        )
        if not text:
            return None
        event_id = f"pearl_{pearl_type.value}"
        return CrewChiefMessage(
            event_id=event_id,
            text=render_template(event_id, {"message": text}),
            priority=CrewChiefPriority.LOW,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=12000,
        )
