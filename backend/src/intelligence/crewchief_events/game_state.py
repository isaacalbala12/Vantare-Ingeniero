from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from shared_telemetry.session_kind import session_kind_from_lmu_int

from .delayed_queue import DelayedMessageQueue, is_message_still_valid, update_hard_part_from_telemetry
from .frame_builder import build_frame_context
from src.intelligence.spotter_grid import adjacent_standing_indices, compute_grid_side


def _class_speed_rank(class_name: str) -> int:
    name = (class_name or "").lower()
    if "hyper" in name or "lmp1" in name:
        return 3
    if "lmp2" in name or "lmp" in name:
        return 2
    return 1


def _enrich_cc_frame(current: dict, strategy: dict | None) -> dict:
    """Normaliza campos LMU/strategy para módulos CC (Task 12+)."""
    enriched = dict(current)
    strategy = strategy or {}

    if enriched.get("frozen_order") and not enriched.get("frozen_order_active"):
        enriched["frozen_order_active"] = True
    if enriched.get("session_stopped") and not enriched.get("frozen_order_active"):
        enriched["frozen_order_active"] = True
    if enriched.get("frozen_order_active") and not str(enriched.get("frozen_order_message") or "").strip():
        enriched["frozen_order_message"] = "Orden congelada. Mantén tu posición."

    if not enriched.get("player_class"):
        enriched["player_class"] = strategy.get("player_class") or enriched.get("vehicle_class") or ""

    player_speed = float(enriched.get("speed_ms") or enriched.get("speed") or 0.0)
    player_class = str(enriched.get("player_class") or "")
    player_rank = _class_speed_rank(player_class)

    frame_comps = list(enriched.get("competitors") or [])
    strat_comps = list(strategy.get("competitors") or [])
    merged = frame_comps if frame_comps else strat_comps
    normalized: list[dict] = []
    for comp in merged:
        if not isinstance(comp, dict):
            continue
        row = dict(comp)
        row["class_name"] = str(row.get("class_name") or row.get("driver_class") or "")
        if row.get("gap_to_player") is None and row.get("gap") is not None:
            row["gap_to_player"] = float(row["gap"])
        comp_speed = float(row.get("speed_ms") or row.get("speed") or 0.0)
        rel = float(row.get("relative_speed_ms") or 0.0)
        if rel <= 0.0 and comp_speed > 0.0 and player_speed > 0.0:
            rel = comp_speed - player_speed
        elif rel <= 0.0 and _class_speed_rank(row["class_name"]) > player_rank:
            gap = float(row.get("gap_to_player") or 999.0)
            if -3.0 < gap < 0.0:
                rel = 8.0
        row["relative_speed_ms"] = rel
        normalized.append(row)
    if normalized:
        enriched["competitors"] = normalized
    return enriched


@dataclass
class CrewChiefGameStateLoop:
    engine: Any
    _previous: Optional[dict] = field(default=None, init=False)
    _start_standing_position: Optional[int] = field(default=None, init=False)
    _session_joined_at: Optional[float] = field(default=None, init=False)
    _grid_side: Optional[str] = field(default=None, init=False)
    _delayed_queue: DelayedMessageQueue = field(default_factory=DelayedMessageQueue, init=False)

    def reset_flag_state(self) -> None:
        """Descarta snapshot previo (p. ej. al reconectar WS)."""
        self._previous = None
        self._start_standing_position = None
        self._session_joined_at = None
        self._grid_side = None
        self._delayed_queue.clear()

    def on_frame(
        self,
        frame: dict,
        *,
        now: float,
        strategy: Optional[dict] = None,
    ) -> None:
        current = _enrich_cc_frame(dict(frame), strategy)
        self._capture_start_standing_position(current)
        self._capture_session_joined_at(current, now)
        self._capture_grid_side(current, strategy)

        if self._start_standing_position is not None:
            current.setdefault("start_standing_position", self._start_standing_position)
        if self._session_joined_at is not None:
            current.setdefault("session_joined_at", self._session_joined_at)
        if self._grid_side is not None:
            current.setdefault("grid_side", self._grid_side)

        ctx = build_frame_context(
            previous=self._previous,
            current=current,
            strategy=strategy or {},
            now_monotonic=now,
        )
        personality = getattr(self.engine, "personality", None)
        if personality is not None:
            ctx.session["personalityProfileId"] = personality.profile_id
        verbosity = getattr(self.engine, "verbosity", None)
        if verbosity is not None:
            verbosity.update_auto_context(current, ctx.session)
            ctx.session["verbosity_level"] = verbosity.level.value
        self._previous = dict(current)

        suite = getattr(self.engine, "crewchief_suite", None)
        messages: list = []
        if suite is not None:
            messages = suite.evaluate(ctx)

        update_hard_part_from_telemetry(self._delayed_queue, current)
        dispatch = getattr(self.engine, "emit_crewchief_messages", None)
        if dispatch is not None:
            for message in messages:
                if self._delayed_queue.enqueue(message, now=now):
                    continue
                dispatch([message])
            for released in self._delayed_queue.ready(
                now,
                ctx,
                validator=is_message_still_valid,
            ):
                dispatch([released])

    def _capture_start_standing_position(self, frame: dict) -> None:
        if self._start_standing_position is not None:
            return

        raw_int = frame.get("session_type_int")
        if raw_int is None:
            return

        if session_kind_from_lmu_int(int(raw_int)) != "race":
            return

        pos = frame.get("standing_position")
        if pos is None:
            return

        self._start_standing_position = int(pos)

    def _capture_session_joined_at(self, frame: dict, now: float) -> None:
        if self._session_joined_at is not None:
            return
        if frame.get("session_type_int") is None:
            return
        self._session_joined_at = now

    def _capture_grid_side(self, frame: dict, strategy: Optional[dict]) -> None:
        if self._grid_side is not None:
            return
        raw_int = frame.get("session_type_int")
        if raw_int is None or session_kind_from_lmu_int(int(raw_int)) != "race":
            return
        lap = int(frame.get("lap_number") or frame.get("completed_laps") or 0)
        if lap > 1:
            return
        competitors = list(frame.get("competitors") or [])
        if not competitors and strategy:
            competitors = list(strategy.get("competitors") or [])
        if not competitors:
            return
        standing = frame.get("standing_position")
        if standing is None:
            return
        fwd_x = float(frame.get("ori_fwd_x") or frame.get("forward_x") or 0.0)
        fwd_z = float(frame.get("ori_fwd_z") or frame.get("forward_z") or 0.0)
        if abs(fwd_x) + abs(fwd_z) < 0.1:
            vel_x = float(frame.get("vel_x") or 0.0)
            vel_z = float(frame.get("vel_z") or 0.0)
            if abs(vel_x) + abs(vel_z) >= 0.5:
                fwd_x, fwd_z = vel_x, vel_z
            else:
                fwd_x, fwd_z = 0.0, 1.0
        adjacent = adjacent_standing_indices(competitors, int(standing))
        side = compute_grid_side(
            competitors,
            player_index=int(frame.get("driver_index") or 0),
            player_forward=(fwd_x, fwd_z),
            adjacent_indices=adjacent or None,
        )
        if side:
            self._grid_side = side
