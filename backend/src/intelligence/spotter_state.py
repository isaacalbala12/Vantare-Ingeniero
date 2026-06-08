"""Máquina de estados del spotter lateral (enter / clear / three-wide)."""
from __future__ import annotations
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from src.intelligence.personality_pack import PersonalityPack
from src.intelligence.spotter_geometry import LateralProximity, build_proximity_message
class SideState(str, Enum):
    CLEAR = "clear"
    CAR_PRESENT = "car_present"
    PENDING_CLEAR = "pending_clear"
@dataclass(frozen=True)
class ProximityTransition:
    message: str
    side: str
    driver_index: int
    driver_class: str
    driver_name: str
    lateral_m: float
    distance_m: float
    severity: str = "INFO"
    audio_priority: int = 2
    category: str = "proximity"
    is_three_wide: bool = False
    is_clear: bool = False
    is_clear_all: bool = False
class SpotterStateMachine:
    """Emite alertas solo en transiciones, no en cada tick."""
    def __init__(
        self,
        *,
        clear_delay_s: float = 0.15,
        overlap_delay_s: float = 2.0,
        hold_repeat_s: float = 3.0,
        closing_speed_ms: float = 12.0,
        exit_hysteresis: float = 1.25,
        still_there_enabled: bool = True,
        personality: Optional[PersonalityPack] = None,
        use_3wide_left_right: bool = True,
        car_width_m: float = 2.0,
    ) -> None:
        self.clear_delay_s = clear_delay_s
        self.overlap_delay_s = overlap_delay_s
        self.hold_repeat_s = hold_repeat_s
        self.closing_speed_ms = closing_speed_ms
        self.exit_hysteresis = exit_hysteresis
        self.still_there_enabled = still_there_enabled
        self.use_3wide_left_right = use_3wide_left_right
        self.car_width_m = car_width_m
        self._personality = personality or PersonalityPack()
        self._left_state = SideState.CLEAR
        self._right_state = SideState.CLEAR
        self._left_clear_since: Optional[float] = None
        self._right_clear_since: Optional[float] = None
        self._left_hit: Optional[LateralProximity] = None
        self._right_hit: Optional[LateralProximity] = None
        self._left_present_since: Optional[float] = None
        self._right_present_since: Optional[float] = None
        self._last_still_there_at: dict[str, float] = {}
        self._closing_emitted: set[str] = set()
        self._hold_emitted: set[str] = set()
        self._three_wide_active = False
        self._three_wide_pending_since: Optional[float] = None
        self._reannounce_at: dict[str, float] = {}
    def set_personality_profile(self, profile_id: str) -> None:
        self._personality.set_profile(profile_id)
    def _spotter_phrase(self, key: str, fallback: str, **kwargs: str) -> str:
        custom = self._personality.spotter_phrase(key, **kwargs)
        if custom:
            return custom
        try:
            return fallback.format(**kwargs)
        except KeyError:
            return fallback
    def _clear_side_key(self, side: str) -> str:
        return "clear_left" if side == "izquierda" else "clear_right"
    def _clear_message(self, side: str) -> str:
        return self._spotter_phrase(
            self._clear_side_key(side),
            f"Despejado {side}",
            side=side,
        )
    def _clear_all_message(self) -> str:
        return self._spotter_phrase("clear_all_round", "Despejado alrededor")
    def _in_the_middle_message(self) -> str:
        return self._spotter_phrase("in_the_middle", "En el medio")
    def reset(self) -> None:
        self._left_state = SideState.CLEAR
        self._right_state = SideState.CLEAR
        self._left_clear_since = None
        self._right_clear_since = None
        self._left_hit = None
        self._right_hit = None
        self._left_present_since = None
        self._right_present_since = None
        self._last_still_there_at.clear()
        self._hold_emitted.clear()
        self._closing_emitted.clear()
        self._three_wide_active = False
        self._three_wide_pending_since = None
        self._reannounce_at.clear()
    def update(
        self,
        hits: list[LateralProximity],
        *,
        player_class: str,
        threshold_m: float,
        now: Optional[float] = None,
    ) -> list[ProximityTransition]:
        ts = now if now is not None else time.monotonic()
        exit_threshold = threshold_m * self.exit_hysteresis
        left_hit = self._best_hit_for_side(hits, "izquierda")
        right_hit = self._best_hit_for_side(hits, "derecha")
        left_present = left_hit is not None and left_hit.lateral_m <= threshold_m
        right_present = right_hit is not None and right_hit.lateral_m <= threshold_m
        if left_hit and not left_present and left_hit.lateral_m <= exit_threshold:
            left_present = self._left_state != SideState.CLEAR
        if right_hit and not right_present and right_hit.lateral_m <= exit_threshold:
            right_present = self._right_state != SideState.CLEAR
        transitions: list[ProximityTransition] = []
        if left_present and right_present and self._is_true_three_wide(hits):
            if not self._three_wide_active:
                bouncing = (
                    self._left_state == SideState.PENDING_CLEAR
                    or self._right_state == SideState.PENDING_CLEAR
                )
                bounce_delay_s = self.hold_repeat_s / 2.0
                if bouncing:
                    if self._three_wide_pending_since is None:
                        self._three_wide_pending_since = ts
                    if (ts - self._three_wide_pending_since) < bounce_delay_s:
                        self._left_state = SideState.CAR_PRESENT
                        self._right_state = SideState.CAR_PRESENT
                        self._left_hit = left_hit
                        self._right_hit = right_hit
                        self._left_clear_since = None
                        self._right_clear_since = None
                        transitions.extend(
                            self._check_reannounce(
                                ts,
                                player_class,
                                left_present,
                                right_present,
                                left_hit,
                                right_hit,
                            )
                        )
                        return transitions
                else:
                    self._three_wide_pending_since = None
                transitions.append(self._three_wide_transition())
                self._three_wide_active = True
            else:
                self._three_wide_pending_since = None
            self._left_state = SideState.CAR_PRESENT
            self._right_state = SideState.CAR_PRESENT
            self._left_hit = left_hit
            self._right_hit = right_hit
            self._left_clear_since = None
            self._right_clear_since = None
            transitions.extend(
                self._check_reannounce(
                    ts,
                    player_class,
                    left_present,
                    right_present,
                    left_hit,
                    right_hit,
                )
            )
            return transitions
        self._three_wide_pending_since = None
        if self._three_wide_active and left_present != right_present:
            cleared_side = "derecha" if not right_present else "izquierda"
            remaining_side = "izquierda" if left_present else "derecha"
            remaining_hit = left_hit if left_present else right_hit
            last_cleared = self._side_hit(cleared_side)
            transitions.append(
                self._build_clear_transition(cleared_side, last_cleared, immediate=True)
            )
            self._set_side_state(cleared_side, SideState.CLEAR)
            self._set_side_clear_since(cleared_side, None)
            self._set_side_hit(cleared_side, None)
            self._set_side_present_since(cleared_side, None)
            self._last_still_there_at.pop(cleared_side, None)
            self._reannounce_at[remaining_side] = ts + self.hold_repeat_s
            self._three_wide_active = False
            if remaining_hit:
                transitions.extend(
                    self._update_side(
                        remaining_side,
                        True,
                        remaining_hit,
                        player_class,
                        ts,
                    )
                )
            transitions.extend(
                self._check_reannounce(
                    ts,
                    player_class,
                    left_present,
                    right_present,
                    left_hit,
                    right_hit,
                )
            )
            return transitions
        if self._three_wide_active and not (left_present and right_present):
            self._three_wide_active = False
        transitions.extend(
            self._update_side(
                "izquierda",
                left_present,
                left_hit,
                player_class,
                ts,
            )
        )
        transitions.extend(
            self._update_side(
                "derecha",
                right_present,
                right_hit,
                player_class,
                ts,
            )
        )
        transitions.extend(
            self._check_reannounce(
                ts,
                player_class,
                left_present,
                right_present,
                left_hit,
                right_hit,
            )
        )
        return self._consolidate_clears(transitions)

    def _is_true_three_wide(self, hits: list[LateralProximity]) -> bool:
        if not self.use_3wide_left_right:
            return True
        signed: list[float] = []
        for hit in hits:
            if hit.side == "derecha":
                signed.append(hit.lateral_m)
            elif hit.side == "izquierda":
                signed.append(-hit.lateral_m)
        if len(signed) < 2:
            return False
        return (max(signed) - min(signed)) > self.car_width_m

    def _three_wide_transition(self) -> ProximityTransition:
        return ProximityTransition(
            message=self._in_the_middle_message(),
            side="three_wide",
            driver_index=-1,
            driver_class="",
            driver_name="",
            lateral_m=0.0,
            distance_m=0.0,
            severity="HIGH",
            audio_priority=3,
            is_three_wide=True,
        )
    def _build_clear_transition(
        self,
        side: str,
        last: Optional[LateralProximity],
        *,
        immediate: bool = False,
    ) -> ProximityTransition:
        return ProximityTransition(
            message=self._clear_message(side),
            side=side,
            driver_index=last.driver_index if last else -1,
            driver_class=last.driver_class if last else "",
            driver_name=last.driver_name if last else "",
            lateral_m=0.0,
            distance_m=0.0,
            severity="INFO",
            audio_priority=2,
            is_clear=True,
        )
    def _consolidate_clears(
        self,
        transitions: list[ProximityTransition],
    ) -> list[ProximityTransition]:
        clears = [t for t in transitions if t.is_clear and not t.is_clear_all]
        if len(clears) < 2:
            return transitions
        non_clear = [t for t in transitions if not t.is_clear]
        non_clear.append(
            ProximityTransition(
                message=self._clear_all_message(),
                side="all",
                driver_index=-1,
                driver_class="",
                driver_name="",
                lateral_m=0.0,
                distance_m=0.0,
                severity="INFO",
                audio_priority=2,
                is_clear=True,
                is_clear_all=True,
            )
        )
        return non_clear
    def _check_reannounce(
        self,
        now: float,
        player_class: str,
        left_present: bool,
        right_present: bool,
        left_hit: Optional[LateralProximity],
        right_hit: Optional[LateralProximity],
    ) -> list[ProximityTransition]:
        transitions: list[ProximityTransition] = []
        for side in ("izquierda", "derecha"):
            at = self._reannounce_at.get(side)
            if at is None or now < at:
                continue
            present = left_present if side == "izquierda" else right_present
            hit = left_hit if side == "izquierda" else right_hit
            if (
                not present
                or hit is None
                or self._side_state(side) != SideState.CAR_PRESENT
            ):
                self._reannounce_at.pop(side, None)
                continue
            message = build_proximity_message(
                player_class,
                hit.driver_class,
                hit.driver_name,
                side,
            )
            transitions.append(
                ProximityTransition(
                    message=message,
                    side=side,
                    driver_index=hit.driver_index,
                    driver_class=hit.driver_class,
                    driver_name=hit.driver_name,
                    lateral_m=hit.lateral_m,
                    distance_m=hit.distance_m,
                )
            )
            self._reannounce_at.pop(side, None)
            self._set_side_present_since(side, now)
            self._last_still_there_at[side] = now
        return transitions
    def _best_hit_for_side(
        self,
        hits: list[LateralProximity],
        side: str,
    ) -> Optional[LateralProximity]:
        side_hits = [h for h in hits if h.side == side]
        if not side_hits:
            return None
        return min(side_hits, key=lambda h: (h.lateral_m, h.distance_m))
    def _side_state(self, side: str) -> SideState:
        return self._left_state if side == "izquierda" else self._right_state
    def _set_side_state(self, side: str, state: SideState) -> None:
        if side == "izquierda":
            self._left_state = state
        else:
            self._right_state = state
    def _side_clear_since(self, side: str) -> Optional[float]:
        return self._left_clear_since if side == "izquierda" else self._right_clear_since
    def _set_side_clear_since(self, side: str, value: Optional[float]) -> None:
        if side == "izquierda":
            self._left_clear_since = value
        else:
            self._right_clear_since = value
    def _side_hit(self, side: str) -> Optional[LateralProximity]:
        return self._left_hit if side == "izquierda" else self._right_hit
    def _set_side_hit(self, side: str, hit: Optional[LateralProximity]) -> None:
        if side == "izquierda":
            self._left_hit = hit
        else:
            self._right_hit = hit
    def _update_side(
        self,
        side: str,
        present: bool,
        hit: Optional[LateralProximity],
        player_class: str,
        now: float,
    ) -> list[ProximityTransition]:
        state = self._side_state(side)
        transitions: list[ProximityTransition] = []
        if present and hit:
            self._set_side_clear_since(side, None)
            if state == SideState.CLEAR:
                message = build_proximity_message(
                    player_class,
                    hit.driver_class,
                    hit.driver_name,
                    side,
                )
                transitions.append(
                    ProximityTransition(
                        message=message,
                        side=side,
                        driver_index=hit.driver_index,
                        driver_class=hit.driver_class,
                        driver_name=hit.driver_name,
                        lateral_m=hit.lateral_m,
                        distance_m=hit.distance_m,
                    )
                )
                self._set_side_state(side, SideState.CAR_PRESENT)
                self._set_side_present_since(side, now)
                self._last_still_there_at[side] = now
            elif state == SideState.PENDING_CLEAR:
                self._set_side_state(side, SideState.CAR_PRESENT)
            elif state == SideState.CAR_PRESENT:
                transitions.extend(self._maybe_hold_or_closing(side, hit, now))
            self._set_side_hit(side, hit)
            return transitions
        if state == SideState.CAR_PRESENT:
            self._set_side_state(side, SideState.PENDING_CLEAR)
            self._set_side_clear_since(side, now)
            self._set_side_present_since(side, None)
            self._last_still_there_at.pop(side, None)
            key_close = f"close:{side}"
            self._hold_emitted.discard(f"hold:{side}")
            self._closing_emitted.discard(key_close)
            return transitions
        if state == SideState.PENDING_CLEAR:
            clear_since = self._side_clear_since(side)
            if clear_since is not None and (now - clear_since) >= self.clear_delay_s:
                last = self._side_hit(side)
                transitions.append(self._build_clear_transition(side, last))
                self._set_side_state(side, SideState.CLEAR)
                self._set_side_hit(side, None)
                self._set_side_clear_since(side, None)
        return transitions
    def _set_side_present_since(self, side: str, value: Optional[float]) -> None:
        if side == "izquierda":
            self._left_present_since = value
        else:
            self._right_present_since = value
    def _side_present_since(self, side: str) -> Optional[float]:
        return self._left_present_since if side == "izquierda" else self._right_present_since
    def _maybe_hold_or_closing(
        self,
        side: str,
        hit: LateralProximity,
        now: float,
    ) -> list[ProximityTransition]:
        transitions: list[ProximityTransition] = []
        since = self._side_present_since(side)
        if since is None:
            return transitions
        duration = now - since
        key_close = f"close:{side}"
        key_hold = f"hold:{side}"
        if self.still_there_enabled:
            last_still = self._last_still_there_at.get(side, since)
            if duration >= self.hold_repeat_s and (now - last_still) >= self.hold_repeat_s:
                transitions.append(
                    ProximityTransition(
                        message=self._spotter_phrase(
                            "still_there",
                            f"Sigue coche por {side}.",
                            side=side,
                        ),
                        side=side,
                        driver_index=hit.driver_index,
                        driver_class=hit.driver_class,
                        driver_name=hit.driver_name,
                        lateral_m=hit.lateral_m,
                        distance_m=hit.distance_m,
                        severity="INFO",
                        audio_priority=2,
                    )
                )
                self._last_still_there_at[side] = now
        elif duration >= self.overlap_delay_s and key_hold not in self._hold_emitted:
            transitions.append(
                ProximityTransition(
                    message=self._spotter_phrase(
                        "hold_line",
                        f"Mantén la línea, coche por {side}.",
                        side=side,
                    ),
                    side=side,
                    driver_index=hit.driver_index,
                    driver_class=hit.driver_class,
                    driver_name=hit.driver_name,
                    lateral_m=hit.lateral_m,
                    distance_m=hit.distance_m,
                    severity="WARNING",
                    audio_priority=3,
                )
            )
            self._hold_emitted.add(key_hold)
        if hit.closing_mps >= self.closing_speed_ms and key_close not in self._closing_emitted:
            transitions.append(
                ProximityTransition(
                    message=self._spotter_phrase(
                        "closing_fast",
                        f"¡Viene rápido por {side}!",
                        side=side,
                    ),
                    side=side,
                    driver_index=hit.driver_index,
                    driver_class=hit.driver_class,
                    driver_name=hit.driver_name,
                    lateral_m=hit.lateral_m,
                    distance_m=hit.distance_m,
                    severity="HIGH",
                    audio_priority=3,
                )
            )
            self._closing_emitted.add(key_close)
        return transitions
