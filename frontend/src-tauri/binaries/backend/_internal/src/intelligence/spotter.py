import logging
import math
import time
import uuid
from typing import Any

from shared_strategy.models import VehicleClassInfo
from src.config import settings
from src.intelligence.personality_pack import PersonalityPack
from src.intelligence.pit_limiter_monitor import PitLimiterMonitor
from src.intelligence.spotter_adapter import resolve_spotter_input
from src.intelligence.cartesian_spotter import (
    detect_cartesian_overlap,
    local_hit_to_lateral_proximity,
    resolve_player_forward_xz,
)
from src.intelligence.spotter_geometry import (
    detect_lateral_proximity,
    detect_path_lateral_proximity,
    resolve_proximity_side,
)
from src.intelligence.spotter_state import ProximityTransition, SpotterStateMachine
from src.models.messages import AlertMessage

logger = logging.getLogger("vantare.spotter")


class SpotterService:
    """Spotter determinista de ultra-baja latencia (20Hz / 50ms)."""

    STOPPED_SPEED_MS = 5.0 / 3.6  # 5 km/h
    STOPPED_GRACE_S = 5.0

    def __init__(
        self,
        broadcast_callback=None,
        vehicle_class_info: VehicleClassInfo | None = None,
        proximity_threshold_m: float | None = None,
        spotter_off_qualifying: bool | None = None,
        spotter_exclude_stopped: bool | None = None,
        invert_lateral: bool = False,
        enabled: bool = True,
        pit_limiter_grace_s: float | None = None,
        pit_limiter_exit_check_s: float | None = None,
        pit_limiter_min_speed_ms: float | None = None,
        pit_limiter_entry_window_s: float | None = None,
        pit_limiter_cooldown_s: float | None = None,
        pit_limiter_disengage_window_s: float = 3.0,
    ) -> None:
        self.broadcast_callback = broadcast_callback
        self.vehicle_class_info = vehicle_class_info or VehicleClassInfo()
        self.enabled = enabled
        self.invert_lateral = invert_lateral
        self.proximity_threshold_m = proximity_threshold_m or settings.SPOTTER_PROXIMITY_THRESHOLD_M
        self.spotter_off_qualifying = (
            spotter_off_qualifying if spotter_off_qualifying is not None else settings.SPOTTER_OFF_QUALIFYING
        )
        self.spotter_exclude_stopped = (
            spotter_exclude_stopped if spotter_exclude_stopped is not None else settings.SPOTTER_EXCLUDE_STOPPED
        )
        self._stopped_since: dict[int, float] = {}
        self._personality = PersonalityPack()
        self._gap_frequency_s = 30.0
        self._car_length_m = settings.SPOTTER_CAR_LENGTH_M
        self._min_speed_ms = settings.SPOTTER_MIN_SPEED_MS
        self._race_start_delay_s = settings.SPOTTER_RACE_START_DELAY_S
        self._race_start_at: float | None = None
        self._enable_gap_messages = True
        self._enable_fuel_messages = True
        self._enable_lap_counter_messages = True
        self._fcy_spotter_paused_until: float = 0.0
        self._last_impact_et_spotter: float = 0.0
        self._last_dent_max_spotter: int = 0
        self._last_accel_spotter_at: float = 0.0
        self._last_seen_lap: int = 0
        self._announced_fuel_critical = False
        self._announced_safety_car = False
        self._announced_last_lap = False

        self._proximity_state = SpotterStateMachine(
            clear_delay_s=settings.SPOTTER_CLEAR_DELAY_S,
            overlap_delay_s=settings.SPOTTER_OVERLAP_DELAY_S,
            hold_repeat_s=settings.SPOTTER_HOLD_REPEAT_S,
            closing_speed_ms=settings.SPOTTER_CLOSING_SPEED_MS,
            personality=self._personality,
            car_width_m=2.0,
        )
        self._pit_limiter = PitLimiterMonitor(
            grace_s=pit_limiter_grace_s if pit_limiter_grace_s is not None else settings.PIT_LIMITER_GRACE_S,
            exit_check_s=(
                pit_limiter_exit_check_s
                if pit_limiter_exit_check_s is not None
                else settings.PIT_LIMITER_EXIT_CHECK_S
            ),
            min_speed_ms=(
                pit_limiter_min_speed_ms
                if pit_limiter_min_speed_ms is not None
                else settings.PIT_LIMITER_MIN_SPEED_MS
            ),
            entry_window_s=(
                pit_limiter_entry_window_s
                if pit_limiter_entry_window_s is not None
                else settings.PIT_LIMITER_ENTRY_WINDOW_S
            ),
            disengage_window_s=pit_limiter_disengage_window_s,
            cooldown_s=pit_limiter_cooldown_s if pit_limiter_cooldown_s is not None else settings.PIT_LIMITER_COOLDOWN_S,
            create_alert=self._create_alert,
        )

    @property
    def pit_limiter_grace_s(self) -> float:
        return self._pit_limiter.grace_s

    @property
    def pit_limiter_exit_check_s(self) -> float:
        return self._pit_limiter.exit_check_s

    @property
    def pit_limiter_min_speed_ms(self) -> float:
        return self._pit_limiter.min_speed_ms

    @property
    def pit_limiter_entry_window_s(self) -> float:
        return self._pit_limiter.entry_window_s

    @property
    def pit_limiter_cooldown_s(self) -> float:
        return self._pit_limiter.cooldown_s

    def apply_runtime_config(self, cfg: dict[str, Any]) -> None:
        if not isinstance(cfg, dict):
            return
        if "personalityProfileId" in cfg:
            self._personality.set_profile(str(cfg["personalityProfileId"]))
            self._proximity_state.set_personality_profile(self._personality.profile_id)
        if "spotterClearDelayS" in cfg:
            self._proximity_state.clear_delay_s = float(cfg["spotterClearDelayS"])
        if "spotterOverlapDelayS" in cfg:
            self._proximity_state.overlap_delay_s = float(cfg["spotterOverlapDelayS"])
        if "spotterHoldRepeatS" in cfg:
            self._proximity_state.hold_repeat_s = float(cfg["spotterHoldRepeatS"])
        if "spotterGapFrequencyS" in cfg:
            self._gap_frequency_s = float(cfg["spotterGapFrequencyS"])
        if "spotterCarLengthM" in cfg:
            self._car_length_m = float(cfg["spotterCarLengthM"])
        if "spotterMinSpeedMs" in cfg:
            # No dejar que el frontend empaquetado (10 m/s) bloquee tráfico lento en pista.
            self._min_speed_ms = min(
                float(cfg["spotterMinSpeedMs"]),
                settings.SPOTTER_MIN_SPEED_MS,
            )
        if "spotterRaceStartDelayS" in cfg:
            self._race_start_delay_s = min(
                float(cfg["spotterRaceStartDelayS"]),
                settings.SPOTTER_RACE_START_DELAY_S,
            )
        if "enableGapMessages" in cfg:
            self._enable_gap_messages = bool(cfg["enableGapMessages"])
        if "enableFuelMessages" in cfg:
            self._enable_fuel_messages = bool(cfg["enableFuelMessages"])
        if "enableLapCounterMessages" in cfg:
            self._enable_lap_counter_messages = bool(cfg["enableLapCounterMessages"])
        if "spotterEnabled" in cfg:
            enabled = bool(cfg["spotterEnabled"])
            # Ignorar false del config_update inicial (frontend legacy); solo spotter_command apaga.
            if enabled:
                self.enabled = True
            logger.info("[Spotter] config spotterEnabled=%s (applied=%s)", cfg["spotterEnabled"], self.enabled)
            self._emit_config_ack()

    def _emit_config_ack(self) -> None:
        if not self.broadcast_callback:
            return
        from src.models.messages import ConfigAckMessage

        self.broadcast_callback(
            ConfigAckMessage(event="config_ack", config=self.runtime_config_snapshot())
        )

    def runtime_config_snapshot(self) -> dict[str, Any]:
        return {
            "spotterEnabled": self.enabled,
            "spotterClearDelayS": self._proximity_state.clear_delay_s,
            "spotterOverlapDelayS": self._proximity_state.overlap_delay_s,
            "spotterHoldRepeatS": self._proximity_state.hold_repeat_s,
            "spotterGapFrequencyS": self._gap_frequency_s,
            "spotterCarLengthM": self._car_length_m,
            "spotterMinSpeedMs": self._min_speed_ms,
            "spotterRaceStartDelayS": self._race_start_delay_s,
        }

    def evaluate_tick(self, state: Any, advice: dict | None = None) -> None:
        if not self.enabled:
            return
        tick_dict = resolve_spotter_input(state, advice)
        if not tick_dict:
            return
        alerts = self.evaluate(tick_dict)
        if alerts and self.broadcast_callback:
            for alert in alerts:
                if alert.category in ("proximity", "damage", "impact"):
                    logger.info("[Spotter] %s: %s", alert.category, alert.message)
                self.broadcast_callback(alert)

    def _is_qualifying(self, tick: dict) -> bool:
        session = tick.get("session_type", "race")
        if isinstance(session, int):
            return session == 2
        return str(session).lower() in ("qualifying", "qualy", "quali")

    def _qualifying_silent(self, tick: dict) -> bool:
        return self.spotter_off_qualifying and self._is_qualifying(tick)

    def _player_speed_ms(self, tick: dict) -> float:
        return math.hypot(float(tick.get("vel_x", 0.0)), float(tick.get("vel_z", 0.0)))

    def _track_race_start(self, tick: dict) -> None:
        if self._race_start_at is not None:
            return
        lap = int(tick.get("lap_number") or 0)
        session = str(tick.get("session_type", "")).lower()
        if lap <= 1 and session in ("race", "6", "r"):
            self._race_start_at = time.monotonic()

    def _effective_threshold(self, tick: dict) -> float:
        vehicle = tick.get("vehicle_name", "")
        player_class = tick.get("player_class", "")
        width = self.vehicle_class_info.get_vehicle_width(vehicle, player_class)
        class_width = self.vehicle_class_info.get_width(player_class) if player_class else 2.0
        width_bonus = max(0.0, (width + class_width) / 2.0 - 2.0)
        return self.proximity_threshold_m + width_bonus * 0.5

    def _update_stopped_tracker(self, competitors: list[dict]) -> set[int]:
        now = time.monotonic()
        excluded: set[int] = set()
        seen: set[int] = set()

        for comp in competitors:
            idx = int(comp.get("driver_index", -1))
            if idx < 0:
                continue
            seen.add(idx)
            if comp.get("in_pits"):
                excluded.add(idx)
                self._stopped_since.pop(idx, None)
                continue
            speed = float(comp.get("speed", 0.0))
            if speed < self.STOPPED_SPEED_MS:
                if idx not in self._stopped_since:
                    self._stopped_since[idx] = now
                elif now - self._stopped_since[idx] >= self.STOPPED_GRACE_S:
                    excluded.add(idx)
            else:
                self._stopped_since.pop(idx, None)

        for idx in list(self._stopped_since):
            if idx not in seen:
                self._stopped_since.pop(idx, None)
        return excluded

    def reset_latched_state(self) -> None:
        """Reinicia flags one-shot (nueva sesión / boxes)."""
        self._last_impact_et_spotter = 0.0
        self._last_dent_max_spotter = 0
        self._last_accel_spotter_at = 0.0
        self._announced_fuel_critical = False
        self._announced_safety_car = False
        self._announced_last_lap = False
        self._proximity_state.reset()

    def _maybe_reset_session(self, tick: dict) -> None:
        lap = int(tick.get("lap_number") or 0)
        if self._last_seen_lap and lap < self._last_seen_lap and lap <= 1:
            self.reset_latched_state()
        self._last_seen_lap = max(self._last_seen_lap, lap)

    def evaluate(self, tick: dict) -> list[AlertMessage]:
        if not self.enabled:
            return []
        self._maybe_reset_session(tick)
        self._track_race_start(tick)
        alerts: list[AlertMessage] = []
        qualifying_silent = self._qualifying_silent(tick)

        if not qualifying_silent:
            alerts.extend(self._eval_gaps(tick))
            alerts.extend(self._eval_proximity(tick))
            alerts.extend(self._eval_last_lap(tick))

        alerts.extend(self._eval_pit_limiters(tick))

        alerts.extend(self._eval_safety_car(tick))
        alerts.extend(self._eval_impact_damage(tick))
        alerts.extend(self._eval_fuel_critical(tick))
        return alerts

    def _eval_pit_limiters(self, tick: dict) -> list[AlertMessage]:
        return self._pit_limiter.evaluate(tick)

    def _eval_gaps(self, tick: dict) -> list[AlertMessage]:
        # enableGapMessages=True → gaps los cubre Crew Chief; spotter no duplica.
        if self._enable_gap_messages:
            return []
        alerts: list[AlertMessage] = []
        gap_ahead = tick.get("gap_ahead", 99.0)
        if gap_ahead < 0.5:
            alerts.append(
                self._create_alert(
                    message=f"Gap con coche de delante estrecho: {gap_ahead:.2f}s",
                    severity="INFO",
                    audio_priority=1,
                    ttl=3,
                    dismissable=True,
                    category="gaps",
                    payload={"gap_ahead": gap_ahead},
                )
            )
        gap_behind = tick.get("gap_behind", 99.0)
        if gap_behind < 0.5:
            alerts.append(
                self._create_alert(
                    message=f"Gap con coche de detrás estrecho: {gap_behind:.2f}s",
                    severity="INFO",
                    audio_priority=1,
                    ttl=3,
                    dismissable=True,
                    category="gaps",
                    payload={"gap_behind": gap_behind},
                )
            )
        return alerts

    def _invert_lateral_hit(self, hit):
        from dataclasses import replace

        flipped = "izquierda" if hit.side == "derecha" else "derecha"
        return replace(hit, side=flipped)

    def _merge_proximity_hits(self, path_hits: list, cart_hits: list) -> list:
        merged: dict[int, Any] = {}
        for hit in cart_hits:
            merged[int(hit.driver_index)] = hit
        for ph in path_hits:
            idx = int(ph.driver_index)
            existing = merged.get(idx)
            if existing is None:
                merged[idx] = ph
                continue
            side = resolve_proximity_side(ph, existing, None, existing.side)
            merged[idx] = ph if side == ph.side else existing
        return list(merged.values())

    def _proximity_allowed(self, tick: dict) -> bool:
        if time.monotonic() < self._fcy_spotter_paused_until:
            return False
        if tick.get("in_pits"):
            return False
        if self._player_speed_ms(tick) < self._min_speed_ms:
            return False
        if self._race_start_at is not None:
            if (time.monotonic() - self._race_start_at) < self._race_start_delay_s:
                return False
        return True

    def _eval_proximity(self, tick: dict) -> list[AlertMessage]:
        if not self._proximity_allowed(tick):
            return []

        competitors = tick.get("competitors") or []
        if not competitors:
            return []

        excluded: set[int] = set()
        if self.spotter_exclude_stopped:
            excluded = self._update_stopped_tracker(competitors)
        else:
            excluded = {int(c["driver_index"]) for c in competitors if c.get("in_pits")}

        threshold = self._effective_threshold(tick)
        track_length_m = float(tick.get("track_length_m") or tick.get("track_length") or 0.0)
        player_speed = self._player_speed_ms(tick)
        path_hits: list = []
        if tick.get("lap_number") is not None and any("path_lateral" in c for c in competitors):
            path_hits = detect_path_lateral_proximity(
                int(tick.get("lap_number", 0)),
                float(tick.get("lap_distance", 0.0)),
                float(tick.get("path_lateral", 0.0)),
                competitors,
                threshold,
                exclude_indices=excluded,
                track_length_m=track_length_m,
                player_speed_ms=player_speed,
                car_length_m=self._car_length_m,
            )

        player_fwd = resolve_player_forward_xz(
            float(tick.get("ori_fwd_x", 0.0)),
            float(tick.get("ori_fwd_z", 0.0)),
            float(tick.get("vel_x", 0.0)),
            float(tick.get("vel_z", 0.0)),
        )
        cart_overlap = detect_cartesian_overlap(
            (tick.get("pos_x", 0.0), tick.get("pos_y", 0.0), tick.get("pos_z", 0.0)),
            player_fwd,
            competitors,
            lateral_threshold_m=threshold,
            car_length_m=self._car_length_m,
            player_speed_ms=player_speed,
            invert_lateral=self.invert_lateral,
            exclude_indices=excluded,
        )
        cart_hits = [local_hit_to_lateral_proximity(h) for h in cart_overlap]

        legacy_cart_hits = detect_lateral_proximity(
            (tick.get("pos_x", 0.0), tick.get("pos_y", 0.0), tick.get("pos_z", 0.0)),
            (tick.get("vel_x", 0.0), tick.get("vel_y", 0.0), tick.get("vel_z", 0.0)),
            competitors,
            threshold,
            exclude_indices=excluded,
        )
        if self.invert_lateral:
            legacy_cart_hits = [self._invert_lateral_hit(h) for h in legacy_cart_hits]

        hits = self._merge_proximity_hits(
            path_hits,
            self._merge_proximity_hits(cart_hits, legacy_cart_hits),
        )
        if not hits:
            transitions = self._proximity_state.update(
                [],
                player_class=str(tick.get("player_class", "")),
                threshold_m=threshold,
            )
        else:
            transitions = self._proximity_state.update(
                hits,
                player_class=str(tick.get("player_class", "")),
                threshold_m=threshold,
            )

        player_class = str(tick.get("player_class", ""))
        return [self._proximity_transition_to_alert(tr, player_class) for tr in transitions]

    def _proximity_transition_to_alert(
        self, tr: ProximityTransition, player_class: str
    ) -> AlertMessage:
        del player_class
        return self._create_alert(
            message=tr.message,
            severity=tr.severity,
            audio_priority=tr.audio_priority,
            ttl=2,
            dismissable=True,
            category=tr.category,
            payload={
                "side": tr.side,
                "distance_m": round(tr.distance_m, 2),
                "lateral_m": round(tr.lateral_m, 2),
                "driver_index": tr.driver_index,
                "clear": tr.is_clear,
                "clear_all": tr.is_clear_all,
                "three_wide": tr.is_three_wide,
            },
        )

    def _eval_safety_car(self, tick: dict) -> list[AlertMessage]:
        sc_active = tick.get("safety_car_active", False) or tick.get("full_course_yellow_active", False)
        if not sc_active:
            self._announced_safety_car = False
            return []
        if self._announced_safety_car:
            return []
        self._announced_safety_car = True
        return [
            self._create_alert(
                message="Safety car desplegado / FCY activo en pista.",
                severity="CRITICAL",
                audio_priority=4,
                ttl=15,
                dismissable=False,
                category="safety_car",
                payload={"safety_car_active": True},
            )
        ]

    def _eval_last_lap(self, tick: dict) -> list[AlertMessage]:
        is_last_lap = tick.get("session_laps_left") == 1.0 or tick.get("is_last_lap", False)
        if not is_last_lap:
            self._announced_last_lap = False
            return []
        if self._announced_last_lap:
            return []
        self._announced_last_lap = True
        return [
            self._create_alert(
                message="¡Última vuelta de la carrera!",
                severity="HIGH",
                audio_priority=2,
                ttl=10,
                dismissable=True,
                category="session",
                payload={"session_laps_left": 1.0},
            )
        ]

    def _eval_impact_damage(self, tick: dict) -> list[AlertMessage]:
        from src.intelligence.damage_report import (
            IMPACT_MAGNITUDE_MIN,
            SPOTTER_ACCEL_COOLDOWN_S,
            SPOTTER_ACCEL_IMPACT_MS2,
            format_impact_damage_message,
            local_accel_magnitude,
        )

        impact_et = float(tick.get("last_impact_et", 0) or 0)
        magnitude = float(tick.get("last_impact_magnitude", 0) or 0)
        trigger = False
        payload: dict[str, Any] = {}

        if impact_et > 0 and magnitude >= IMPACT_MAGNITUDE_MIN:
            if impact_et != self._last_impact_et_spotter:
                self._last_impact_et_spotter = impact_et
                trigger = True
                payload = {"last_impact_et": impact_et, "last_impact_magnitude": magnitude}
        else:
            now = time.monotonic()
            dent_max = int(tick.get("dent_severity_max", 0) or 0)
            accel = local_accel_magnitude(tick)
            if dent_max > self._last_dent_max_spotter and dent_max >= 1:
                self._last_dent_max_spotter = dent_max
                trigger = True
                payload = {"dent_severity_max": dent_max, "source": "dent_delta"}
            elif (
                accel >= SPOTTER_ACCEL_IMPACT_MS2
                and (now - self._last_accel_spotter_at) >= SPOTTER_ACCEL_COOLDOWN_S
            ):
                self._last_accel_spotter_at = now
                trigger = True
                payload = {"local_accel_ms2": round(accel, 1), "source": "accel_spike"}

        if not trigger:
            return []

        message = format_impact_damage_message(tick)
        if not message:
            return []
        return [
            self._create_alert(
                message=message,
                severity="HIGH",
                audio_priority=3,
                ttl=8,
                dismissable=True,
                category="damage",
                payload=payload,
            )
        ]

    def _eval_fuel_critical(self, tick: dict) -> list[AlertMessage]:
        # enableFuelMessages=True → avisos de fuel los cubre Crew Chief; spotter no duplica.
        if self._enable_fuel_messages:
            return []
        fuel_laps = tick.get("fuel_laps_remaining", tick.get("estimated_laps_remaining", 99.0))
        if fuel_laps >= 1.0:
            self._announced_fuel_critical = False
            return []

        pit_stops = tick.get("pit_stops_needed")
        fuel_in_tank = tick.get("fuel_in_tank")
        fuel_needed = tick.get("fuel_needed_to_finish")
        if (
            pit_stops == 0
            and fuel_in_tank is not None
            and fuel_needed is not None
            and float(fuel_in_tank) >= float(fuel_needed)
        ):
            return []

        if self._announced_fuel_critical:
            return []
        self._announced_fuel_critical = True
        return [
            self._create_alert(
                message=f"¡Combustible crítico! Menos de 1 vuelta restante ({float(fuel_laps):.2f} laps).",
                severity="CRITICAL",
                audio_priority=4,
                ttl=10,
                dismissable=False,
                category="fuel",
                payload={"fuel_laps_remaining": fuel_laps},
            )
        ]

    def _create_alert(
        self,
        message: str,
        severity: str,
        audio_priority: int,
        ttl: int,
        dismissable: bool,
        category: str,
        payload: dict[str, Any],
    ) -> AlertMessage:
        return AlertMessage(
            event="alert",
            alert_id=str(uuid.uuid4()),
            category=category,
            message=message,
            audio_priority=str(audio_priority),
            severity=severity,
            ttl=ttl,
            dismissable=dismissable,
            payload={
                "severity": severity,
                "ttl": ttl,
                "dismissable": dismissable,
                **payload,
                **(
                    {"service": "spotter"}
                    if category
                    in (
                        "proximity",
                        "pit_limiter",
                        "fuel",
                        "safety_car",
                        "damage",
                        "impact",
                        "puncture",
                        "limiter",
                    )
                    else {}
                ),
            },
        )
