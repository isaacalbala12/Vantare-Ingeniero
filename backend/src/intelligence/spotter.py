import time
import uuid
import math
from typing import Any, Dict, List, Optional

from src.config import settings
from src.models.messages import AlertMessage
from src.intelligence.fuel_safety import fuel_critical_from_tick
from src.intelligence.damage_report import (
    IMPACT_MAGNITUDE_MIN,
    CRASH_RETRY_MESSAGES,
    detect_crash_g,
    format_damage_summary,
    format_impact_damage_message,
    format_puncture_message,
)
from src.intelligence.flags_monitor import FCY_PHASE_MESSAGES
from src.intelligence.spotter_adapter import resolve_spotter_input
from src.intelligence.pit_limiter_monitor import PitLimiterMonitor
from src.intelligence.spotter_state import SpotterStateMachine, ProximityTransition
from src.intelligence.spotter_geometry import (
    LateralProximity,
    detect_lateral_proximity,
    detect_path_lateral_proximity,
    enrich_hits_with_closing_speed,
    resolve_proximity_side,
)
from src.intelligence.cartesian_spotter import (
    detect_cartesian_overlap,
    local_hit_to_lateral_proximity,
    resolve_player_forward_xz,
)
from shared_telemetry.session_kind import is_race_session
from shared_strategy.models import VehicleClassInfo


class SpotterService:
    """Spotter determinista de ultra-baja latencia (20Hz / 50ms)."""

    STOPPED_SPEED_MS = 5.0 / 3.6  # 5 km/h
    STOPPED_GRACE_S = 5.0

    def __init__(
        self,
        broadcast_callback=None,
        vehicle_class_info: Optional[VehicleClassInfo] = None,
        proximity_threshold_m: Optional[float] = None,
        spotter_off_qualifying: Optional[bool] = None,
        spotter_exclude_stopped: Optional[bool] = None,
        pit_limiter_grace_s: Optional[float] = None,
        pit_limiter_exit_check_s: Optional[float] = None,
        pit_limiter_min_speed_ms: Optional[float] = None,
        pit_limiter_entry_window_s: Optional[float] = None,
        pit_limiter_disengage_window_s: Optional[float] = None,
        pit_limiter_cooldown_s: Optional[float] = None,
        invert_lateral: Optional[bool] = None,
        enabled: bool = False,
    ) -> None:
        self.broadcast_callback = broadcast_callback
        self.vehicle_class_info = vehicle_class_info or VehicleClassInfo()
        self.enabled = bool(enabled)
        self.proximity_threshold_m = proximity_threshold_m or settings.SPOTTER_PROXIMITY_THRESHOLD_M
        self.spotter_off_qualifying = (
            spotter_off_qualifying if spotter_off_qualifying is not None else settings.SPOTTER_OFF_QUALIFYING
        )
        self.spotter_exclude_stopped = (
            spotter_exclude_stopped if spotter_exclude_stopped is not None else settings.SPOTTER_EXCLUDE_STOPPED
        )
        self._stopped_since: dict[int, float] = {}
        self._warned_damage = False
        self._last_impact_et = 0.0
        self._warned_safety_car = False
        self._warned_last_lap = False
        self._warned_fuel_critical = False
        self._puncture_announced: set[int] = set()
        self._puncture_pending_at: dict[int, float] = {}
        self._crash_active = False
        self._crash_started_at: float | None = None
        self._crash_retry_index = 0
        self._last_fcy_phase = 0
        self.pit_limiter_grace_s = (
            pit_limiter_grace_s if pit_limiter_grace_s is not None else settings.PIT_LIMITER_GRACE_S
        )
        self.pit_limiter_exit_check_s = (
            pit_limiter_exit_check_s
            if pit_limiter_exit_check_s is not None
            else settings.PIT_LIMITER_EXIT_CHECK_S
        )
        self.pit_limiter_min_speed_ms = (
            pit_limiter_min_speed_ms
            if pit_limiter_min_speed_ms is not None
            else settings.PIT_LIMITER_MIN_SPEED_MS
        )
        self.pit_limiter_entry_window_s = (
            pit_limiter_entry_window_s
            if pit_limiter_entry_window_s is not None
            else settings.PIT_LIMITER_ENTRY_WINDOW_S
        )
        self.pit_limiter_disengage_window_s = (
            pit_limiter_disengage_window_s
            if pit_limiter_disengage_window_s is not None
            else settings.PIT_LIMITER_DISENGAGE_WINDOW_S
        )
        self.pit_limiter_cooldown_s = (
            pit_limiter_cooldown_s if pit_limiter_cooldown_s is not None else settings.PIT_LIMITER_COOLDOWN_S
        )
        self.invert_lateral = (
            invert_lateral if invert_lateral is not None else settings.SPOTTER_INVERT_LATERAL
        )
        self._proximity_state = SpotterStateMachine(
            clear_delay_s=settings.SPOTTER_CLEAR_DELAY_S,
            overlap_delay_s=settings.SPOTTER_OVERLAP_DELAY_S,
            hold_repeat_s=settings.SPOTTER_HOLD_REPEAT_S,
            closing_speed_ms=settings.SPOTTER_CLOSING_SPEED_MS,
            use_3wide_left_right=settings.SPOTTER_USE_3WIDE_LEFT_RIGHT,
            car_width_m=2.0,
        )
        self._pit_limiter = PitLimiterMonitor(
            grace_s=self.pit_limiter_grace_s,
            exit_check_s=self.pit_limiter_exit_check_s,
            min_speed_ms=self.pit_limiter_min_speed_ms,
            entry_window_s=self.pit_limiter_entry_window_s,
            disengage_window_s=self.pit_limiter_disengage_window_s,
            cooldown_s=self.pit_limiter_cooldown_s,
            create_alert=self._create_alert,
        )
        self._race_start_at: Optional[float] = None
        self._min_speed_ms = settings.SPOTTER_MIN_SPEED_MS
        self._car_length_m = settings.SPOTTER_CAR_LENGTH_M
        self._gap_frequency_s = settings.SPOTTER_GAP_FREQUENCY_S
        self._race_start_delay_s = settings.SPOTTER_RACE_START_DELAY_S
        self._fcy_spotter_paused_until: float = 0.0
        self._fcy_sc_active_last: bool = False
        self._last_forward_xz: Optional[tuple[float, float]] = None
        self._fcy_pause_min_s = settings.SPOTTER_FCY_PAUSE_MIN_S
        self._fcy_pause_max_s = settings.SPOTTER_FCY_PAUSE_MAX_S
        self._fcy_pause_speed_max_ms = 50.0
        self._clear_ttl_ms = settings.SPOTTER_CLEAR_TTL_MS
        self._last_gap_alert_at: float = 0.0
        self._enable_gap_messages = True
        self._enable_lap_counter_messages = True
        self._enable_fuel_messages = True

    def apply_runtime_config(self, cfg: dict) -> None:
        if "spotterClearDelayS" in cfg:
            self._proximity_state.clear_delay_s = float(cfg["spotterClearDelayS"])
        if "spotterOverlapDelayS" in cfg:
            self._proximity_state.overlap_delay_s = float(cfg["spotterOverlapDelayS"])
        if "spotterHoldRepeatS" in cfg:
            self._proximity_state.hold_repeat_s = float(cfg["spotterHoldRepeatS"])
        if "spotterProximityThresholdM" in cfg:
            self.proximity_threshold_m = float(cfg["spotterProximityThresholdM"])
        if "spotterCarLengthM" in cfg:
            self._car_length_m = float(cfg["spotterCarLengthM"])
        if "spotterGapFrequencyS" in cfg:
            self._gap_frequency_s = float(cfg["spotterGapFrequencyS"])
        if "spotterMinSpeedMs" in cfg:
            self._min_speed_ms = float(cfg["spotterMinSpeedMs"])
        if "spotterRaceStartDelayS" in cfg:
            self._race_start_delay_s = float(cfg["spotterRaceStartDelayS"])
        if "spotterOffQualifying" in cfg:
            self.spotter_off_qualifying = bool(cfg["spotterOffQualifying"])
        if "spotterExcludeStopped" in cfg:
            self.spotter_exclude_stopped = bool(cfg["spotterExcludeStopped"])
        if "personalityProfileId" in cfg:
            self._proximity_state.set_personality_profile(str(cfg["personalityProfileId"]))
        if "enableGapMessages" in cfg:
            self._enable_gap_messages = bool(cfg["enableGapMessages"])
        if "enableLapCounterMessages" in cfg:
            self._enable_lap_counter_messages = bool(cfg["enableLapCounterMessages"])
        if "enableFuelMessages" in cfg:
            self._enable_fuel_messages = bool(cfg["enableFuelMessages"])

    def runtime_config_snapshot(self) -> dict:
        return {
            "spotterClearDelayS": self._proximity_state.clear_delay_s,
            "spotterOverlapDelayS": self._proximity_state.overlap_delay_s,
            "spotterHoldRepeatS": self._proximity_state.hold_repeat_s,
            "spotterGapFrequencyS": self._gap_frequency_s,
            "spotterCarLengthM": self._car_length_m,
            "spotterMinSpeedMs": self._min_speed_ms,
            "spotterRaceStartDelayS": self._race_start_delay_s,
            "spotterOffQualifying": self.spotter_off_qualifying,
            "spotterExcludeStopped": self.spotter_exclude_stopped,
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
                self.broadcast_callback(alert)

    def _is_qualifying(self, tick: dict) -> bool:
        session = tick.get("session_type", "race")
        if isinstance(session, int):
            return session == 2
        return str(session).lower() in ("qualifying", "qualy", "quali")

    def _qualifying_silent(self, tick: dict) -> bool:
        return self.spotter_off_qualifying and self._is_qualifying(tick)

    def _cc_owns_message(self, tick: dict, cc_enabled: bool) -> bool:
        """CC suite owns gap/fuel/lap alerts in race when the matching enable_* flag is on."""
        return cc_enabled and is_race_session(tick, None)

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

    def evaluate(self, tick: dict) -> List[AlertMessage]:
        if not self.enabled:
            return []
        alerts: List[AlertMessage] = []
        qualifying_silent = self._qualifying_silent(tick)

        alerts.extend(self._eval_pit_limiters(tick))
        alerts.extend(self._eval_impact_damage(tick))
        alerts.extend(self._eval_puncture(tick))
        alerts.extend(self._eval_crash(tick))

        if not qualifying_silent:
            alerts.extend(self._eval_gaps(tick))
            alerts.extend(self._eval_proximity(tick))
            alerts.extend(self._eval_last_lap(tick))

        alerts.extend(self._eval_fcy_phases(tick))
        alerts.extend(self._eval_fuel_critical(tick))
        return alerts

    def _eval_pit_limiters(self, tick: dict) -> List[AlertMessage]:
        return self._pit_limiter.evaluate(tick)

    def _eval_gaps(self, tick: dict) -> List[AlertMessage]:
        if self._cc_owns_message(tick, self._enable_gap_messages):
            return []
        now = time.monotonic()
        if now - self._last_gap_alert_at < self._gap_frequency_s:
            return []
        alerts: List[AlertMessage] = []
        gap_ahead = tick.get("gap_ahead", 99.0)
        if gap_ahead < 0.5:
            alerts.append(self._create_alert(
                message=f"Gap con coche de delante estrecho: {gap_ahead:.2f}s",
                severity="INFO",
                audio_priority=1,
                ttl=3,
                dismissable=True,
                category="gaps",
                payload={"gap_ahead": gap_ahead},
            ))
        gap_behind = tick.get("gap_behind", 99.0)
        if gap_behind < 0.5:
            alerts.append(self._create_alert(
                message=f"Gap con coche de detrás estrecho: {gap_behind:.2f}s",
                severity="INFO",
                audio_priority=1,
                ttl=3,
                dismissable=True,
                category="gaps",
                payload={"gap_behind": gap_behind},
            ))
        if alerts:
            self._last_gap_alert_at = now
        return alerts

    def _eval_impact_damage(self, tick: dict) -> List[AlertMessage]:
        impact_et = float(tick.get("last_impact_et", 0) or 0)
        magnitude = float(tick.get("last_impact_magnitude", 0) or 0)
        if (
            impact_et > 0
            and impact_et != self._last_impact_et
            and magnitude >= IMPACT_MAGNITUDE_MIN
        ):
            self._last_impact_et = impact_et
            self._warned_damage = True
            severity = "CRITICAL" if float(tick.get("damage_aero", 0) or 0) >= 60 else "WARNING"
            return [self._create_alert(
                message=format_impact_damage_message(tick),
                severity=severity,
                audio_priority=4 if severity == "CRITICAL" else 3,
                ttl=12,
                dismissable=True,
                category="damage",
                payload={
                    "damage_aero": tick.get("damage_aero", 0.0),
                    "suspension_damage": tick.get("suspension_damage", 0.0),
                    "last_impact_magnitude": magnitude,
                },
            )]
        return []

    def _eval_damage(self, tick: dict) -> List[AlertMessage]:
        alerts = self._eval_impact_damage(tick)
        if alerts:
            return alerts

        has_damage = (
            tick.get("damage_aero", 0.0) > 0.0
            or tick.get("suspension_damage", 0.0) > 0.0
            or int(tick.get("dent_severity_max", 0) or 0) > 0
            or (
                isinstance(tick.get("damage"), dict)
                and any(v > 0.0 for v in tick.get("damage").values())
            )
        )
        if not has_damage:
            self._warned_damage = False
            return []
        if self._warned_damage:
            return []
        self._warned_damage = True
        return [self._create_alert(
            message=format_damage_summary(tick),
            severity="WARNING",
            audio_priority=3,
            ttl=10,
            dismissable=True,
            category="damage",
            payload={
                "damage_aero": tick.get("damage_aero", 0.0),
                "suspension_damage": tick.get("suspension_damage", 0.0),
            },
        )]

    def _eval_puncture(self, tick: dict) -> List[AlertMessage]:
        now = time.monotonic()
        alerts: List[AlertMessage] = []
        for i, suffix in enumerate(("fl", "fr", "rl", "rr")):
            is_flat = bool(tick.get(f"tyre_flat_{suffix}", False))
            if not is_flat:
                self._puncture_announced.discard(i)
                self._puncture_pending_at.pop(i, None)
                continue
            if i in self._puncture_announced:
                continue
            if i not in self._puncture_pending_at:
                self._puncture_pending_at[i] = now + 5.0
                continue
            if now < self._puncture_pending_at[i]:
                continue
            self._puncture_announced.add(i)
            alerts.append(
                self._create_alert(
                    message=format_puncture_message(i),
                    severity="CRITICAL",
                    audio_priority=4,
                    ttl=12,
                    dismissable=True,
                    category="damage",
                    payload={"wheel_index": i},
                )
            )
        return alerts

    def _eval_crash(self, tick: dict) -> List[AlertMessage]:
        now = time.monotonic()
        in_pits = bool(tick.get("in_pits", False))

        if in_pits and self._crash_active:
            self._crash_active = False
            self._crash_started_at = None
            self._crash_retry_index = 0
            return []

        if detect_crash_g(tick) and not self._crash_active:
            self._crash_active = True
            self._crash_started_at = now
            self._crash_retry_index = 0

        if not self._crash_active or self._crash_started_at is None:
            return []

        elapsed = now - self._crash_started_at
        retry_delays = (0.0, 8.0, 16.0)
        alerts: List[AlertMessage] = []
        while (
            self._crash_retry_index < len(CRASH_RETRY_MESSAGES)
            and elapsed >= retry_delays[self._crash_retry_index]
        ):
            alerts.append(
                self._create_alert(
                    message=CRASH_RETRY_MESSAGES[self._crash_retry_index],
                    severity="CRITICAL",
                    audio_priority=4,
                    ttl=10,
                    dismissable=False,
                    category="damage",
                    payload={"crash_retry": self._crash_retry_index},
                )
            )
            self._crash_retry_index += 1

        if self._crash_retry_index >= len(CRASH_RETRY_MESSAGES):
            self._crash_active = False
        return alerts

    def _eval_fcy_phases(self, tick: dict) -> List[AlertMessage]:
        phase = int(tick.get("yellow_flag_state", 0) or 0)
        sc_active = tick.get("safety_car_active", False) or tick.get("full_course_yellow_active", False)

        if not sc_active and phase == 0:
            self._last_fcy_phase = 0
            self._warned_safety_car = False
            return []

        if phase == self._last_fcy_phase:
            if sc_active and not self._warned_safety_car and phase == 0:
                self._warned_safety_car = True
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
            return []

        self._last_fcy_phase = phase
        if phase in FCY_PHASE_MESSAGES:
            msg, prio = FCY_PHASE_MESSAGES[phase]
            self._warned_safety_car = True
            return [
                self._create_alert(
                    message=msg,
                    severity="CRITICAL" if prio >= 4 else "WARNING",
                    audio_priority=prio,
                    ttl=15,
                    dismissable=False,
                    category="safety_car",
                    payload={"fcy_phase": phase},
                )
            ]
        return []

    def _collect_proximity_hits(
        self,
        tick: dict,
        competitors: list[dict],
        threshold: float,
        excluded: set[int],
    ) -> list[LateralProximity]:
        """Fusiona path, cartesian y velocidad; reconcilia izquierda/derecha por rival."""
        lap = int(tick.get("lap_number", 0) or 0)
        lap_dist = float(tick.get("lap_distance", 0.0))
        player_lateral = float(tick.get("path_lateral", 0.0))
        vel_x = float(tick.get("vel_x", 0.0))
        vel_z = float(tick.get("vel_z", 0.0))
        player_vel = (vel_x, float(tick.get("vel_y", 0.0)), vel_z)
        player_speed = math.hypot(vel_x, vel_z)
        fwd = resolve_player_forward_xz(
            float(tick.get("ori_fwd_x", 0.0)),
            float(tick.get("ori_fwd_z", 0.0)),
            vel_x,
            vel_z,
            self._last_forward_xz,
        )
        self._last_forward_xz = fwd
        player_pos = (
            float(tick.get("pos_x", 0.0)),
            float(tick.get("pos_y", 0.0)),
            float(tick.get("pos_z", 0.0)),
        )

        path_hits = detect_path_lateral_proximity(
            lap,
            lap_dist,
            player_lateral,
            competitors,
            threshold,
            exclude_indices=excluded,
        )
        path_by_idx = {h.driver_index: h for h in path_hits}

        cart_by_idx = {
            h.driver_index: local_hit_to_lateral_proximity(h)
            for h in detect_cartesian_overlap(
                player_pos,
                fwd,
                competitors,
                lateral_threshold_m=threshold,
                car_length_m=self._car_length_m,
                player_speed_ms=player_speed,
                invert_lateral=self.invert_lateral,
                exclude_indices=excluded,
            )
        }

        vel_by_idx = {
            h.driver_index: h
            for h in detect_lateral_proximity(
                player_pos,
                player_vel,
                competitors,
                threshold,
                exclude_indices=excluded,
                forward_xz=fwd,
                invert_lateral=self.invert_lateral,
            )
        }

        merged: list[LateralProximity] = []
        for idx in set(path_by_idx) | set(cart_by_idx) | set(vel_by_idx):
            if idx in excluded:
                continue
            path_h = path_by_idx.get(idx)
            cart_h = cart_by_idx.get(idx)
            vel_h = vel_by_idx.get(idx)
            if path_h is not None:
                base, source = path_h, "path"
            elif cart_h is not None:
                base, source = cart_h, "cartesian"
            elif vel_h is not None:
                base, source = vel_h, "velocity"
            else:
                continue

            side = resolve_proximity_side(path_h, cart_h, vel_h, base.side)
            merged.append(
                LateralProximity(
                    driver_index=base.driver_index,
                    driver_class=base.driver_class,
                    driver_name=base.driver_name,
                    lateral_m=base.lateral_m,
                    side=side,
                    distance_m=base.distance_m,
                    closing_mps=base.closing_mps,
                    detection_source=source,
                    longitudinal_m=base.longitudinal_m,
                )
            )

        merged.sort(key=lambda h: (h.lateral_m, h.distance_m))
        return enrich_hits_with_closing_speed(merged, player_vel, competitors)

    def _eval_proximity(self, tick: dict) -> List[AlertMessage]:
        if self._proximity_paused_for_fcy(tick):
            return []
        if bool(tick.get("in_pits", False)):
            self._proximity_state.reset()
            self._last_forward_xz = None
            return []

        player_speed = math.hypot(float(tick.get("vel_x", 0.0)), float(tick.get("vel_z", 0.0)))
        if player_speed < self._min_speed_ms:
            return []

        phase = str(tick.get("session_phase", tick.get("session_type", "race"))).upper()
        lap_number = int(tick.get("lap_number", 0) or 0)
        if lap_number > 1 or phase not in ("RACE", "GREEN"):
            self._race_start_at = None
        elif phase in ("RACE", "GREEN") and lap_number <= 1:
            if self._race_start_at is None:
                self._race_start_at = time.monotonic()
            if time.monotonic() - self._race_start_at < self._race_start_delay_s:
                return []

        competitors = tick.get("competitors") or []
        if not competitors:
            transitions = self._proximity_state.update(
                [],
                player_class=str(tick.get("player_class", "") or ""),
                threshold_m=self._effective_threshold(tick),
                now=time.monotonic(),
            )
            return [self._transition_to_alert(tr) for tr in transitions]

        excluded: set[int] = set()
        if self.spotter_exclude_stopped:
            excluded = self._update_stopped_tracker(competitors)
        else:
            excluded = {int(c["driver_index"]) for c in competitors if c.get("in_pits")}

        threshold = self._effective_threshold(tick)
        hits = self._collect_proximity_hits(tick, competitors, threshold, excluded)
        hit_sources = {h.driver_index: h.detection_source for h in hits if h.detection_source}
        transitions = self._proximity_state.update(
            hits,
            player_class=str(tick.get("player_class", "") or ""),
            threshold_m=threshold,
            now=time.monotonic(),
        )
        alerts: List[AlertMessage] = []
        for tr in transitions:
            alert = self._transition_to_alert(tr)
            src = hit_sources.get(tr.driver_index)
            if src and not tr.is_clear and not tr.is_clear_all:
                alert.payload["detection_source"] = src
            alerts.append(alert)
        return alerts

    def _proximity_paused_for_fcy(self, tick: dict) -> bool:
        now = time.monotonic()
        if now < self._fcy_spotter_paused_until:
            return True
        sc = bool(tick.get("safety_car_active") or tick.get("full_course_yellow_active"))
        speed = float(tick.get("speed_ms") or tick.get("speed") or 0.0)
        if sc and not self._fcy_sc_active_last and speed < self._fcy_pause_speed_max_ms:
            self._fcy_spotter_paused_until = now + self._fcy_pause_min_s
            self._fcy_sc_active_last = True
            return True
        self._fcy_sc_active_last = sc
        return False

    def _transition_to_alert(self, transition: ProximityTransition) -> AlertMessage:
        payload: Dict[str, Any] = {
            "side": transition.side,
            "driver_index": transition.driver_index,
            "driver_class": transition.driver_class,
            "driver_name": transition.driver_name,
            "lateral_m": round(transition.lateral_m, 2),
            "distance_m": round(transition.distance_m, 2),
        }
        if transition.is_clear:
            payload["clear"] = True
        if transition.is_clear_all:
            payload["clear_all"] = True
        if transition.is_three_wide:
            payload["three_wide"] = True
        ttl = 3 if transition.is_three_wide else 2
        if transition.is_clear or transition.is_clear_all:
            ttl = max(2, int(self._clear_ttl_ms / 1000))
            payload["ttl_ms"] = self._clear_ttl_ms
        return self._create_alert(
            message=transition.message,
            severity=transition.severity,
            audio_priority=transition.audio_priority,
            ttl=ttl,
            dismissable=True,
            category="proximity",
            payload=payload,
        )

    def _eval_last_lap(self, tick: dict) -> List[AlertMessage]:
        if self._cc_owns_message(tick, self._enable_lap_counter_messages):
            return []
        laps_left = tick.get("session_laps_left")
        is_last_lap = laps_left == 1.0 or tick.get("is_last_lap", False)
        if laps_left is not None and float(laps_left) > 1.0:
            self._warned_last_lap = False
        if not is_last_lap:
            return []
        if self._warned_last_lap:
            return []
        self._warned_last_lap = True
        return [self._create_alert(
            message="¡Última vuelta de la carrera!",
            severity="HIGH",
            audio_priority=2,
            ttl=10,
            dismissable=True,
            category="session",
            payload={"session_laps_left": 1.0},
        )]

    def _eval_fuel_critical(self, tick: dict) -> List[AlertMessage]:
        if self._cc_owns_message(tick, self._enable_fuel_messages):
            return []
        if not fuel_critical_from_tick(tick):
            self._warned_fuel_critical = False
            return []
        if self._warned_fuel_critical:
            return []
        self._warned_fuel_critical = True
        fuel_laps = tick.get("fuel_laps_remaining", tick.get("estimated_laps_remaining", 99.0))
        return [self._create_alert(
            message=f"¡Combustible crítico! Menos de 1 vuelta restante ({fuel_laps:.2f} laps).",
            severity="CRITICAL",
            audio_priority=4,
            ttl=10,
            dismissable=False,
            category="fuel",
            payload={"fuel_laps_remaining": fuel_laps},
        )]

    def _create_alert(
        self,
        message: str,
        severity: str,
        audio_priority: int,
        ttl: int,
        dismissable: bool,
        category: str,
        payload: Dict[str, Any],
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
                "service": "spotter",
                "severity": severity,
                "ttl": ttl,
                "dismissable": dismissable,
                **payload,
            },
        )
