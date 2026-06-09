import time
import uuid
from typing import Any

from shared_strategy.models import VehicleClassInfo
from src.config import settings
from src.intelligence.spotter_adapter import resolve_spotter_input
from src.intelligence.spotter_geometry import build_proximity_message, detect_lateral_proximity
from src.models.messages import AlertMessage


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
    ) -> None:
        self.broadcast_callback = broadcast_callback
        self.vehicle_class_info = vehicle_class_info or VehicleClassInfo()
        self.enabled = True
        self.proximity_threshold_m = proximity_threshold_m or settings.SPOTTER_PROXIMITY_THRESHOLD_M
        self.spotter_off_qualifying = (
            spotter_off_qualifying if spotter_off_qualifying is not None else settings.SPOTTER_OFF_QUALIFYING
        )
        self.spotter_exclude_stopped = (
            spotter_exclude_stopped if spotter_exclude_stopped is not None else settings.SPOTTER_EXCLUDE_STOPPED
        )
        self._stopped_since: dict[int, float] = {}

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

    def evaluate(self, tick: dict) -> list[AlertMessage]:
        if not self.enabled:
            return []
        alerts: list[AlertMessage] = []
        qualifying_silent = self._qualifying_silent(tick)

        if not qualifying_silent:
            alerts.extend(self._eval_pit_limiters(tick))
            alerts.extend(self._eval_gaps(tick))
            alerts.extend(self._eval_damage(tick))
            alerts.extend(self._eval_proximity(tick))
            alerts.extend(self._eval_last_lap(tick))

        alerts.extend(self._eval_safety_car(tick))
        alerts.extend(self._eval_fuel_critical(tick))
        return alerts

    def _eval_pit_limiters(self, tick: dict) -> list[AlertMessage]:
        alerts: list[AlertMessage] = []
        if tick.get("in_pits", False) and not tick.get("pit_limiter_active", False):
            alerts.append(
                self._create_alert(
                    message="Pit limiter no activado al entrar en boxes.",
                    severity="CRITICAL",
                    audio_priority=4,
                    ttl=5,
                    dismissable=True,
                    category="limiter",
                    payload={"in_pits": True, "pit_limiter_active": False},
                )
            )
        if not tick.get("in_pits", False) and tick.get("pit_limiter_active", False):
            alerts.append(
                self._create_alert(
                    message="Pit limiter no desactivado al salir de boxes.",
                    severity="WARNING",
                    audio_priority=3,
                    ttl=5,
                    dismissable=True,
                    category="limiter",
                    payload={"in_pits": False, "pit_limiter_active": True},
                )
            )
        return alerts

    def _eval_gaps(self, tick: dict) -> list[AlertMessage]:
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

    def _eval_damage(self, tick: dict) -> list[AlertMessage]:
        has_damage = (
            tick.get("damage_aero", 0.0) > 0.0
            or tick.get("suspension_damage", 0.0) > 0.0
            or (isinstance(tick.get("damage"), dict) and any(v > 0.0 for v in tick.get("damage").values()))
        )
        if not has_damage:
            return []
        return [
            self._create_alert(
                message="Daños detectados en el monoplaza.",
                severity="WARNING",
                audio_priority=3,
                ttl=10,
                dismissable=True,
                category="damage",
                payload={
                    "damage_aero": tick.get("damage_aero", 0.0),
                    "suspension_damage": tick.get("suspension_damage", 0.0),
                },
            )
        ]

    def _eval_proximity(self, tick: dict) -> list[AlertMessage]:
        competitors = tick.get("competitors") or []
        if not competitors:
            return []

        excluded: set[int] = set()
        if self.spotter_exclude_stopped:
            excluded = self._update_stopped_tracker(competitors)
        else:
            excluded = {int(c["driver_index"]) for c in competitors if c.get("in_pits")}

        threshold = self._effective_threshold(tick)
        hits = detect_lateral_proximity(
            (tick.get("pos_x", 0.0), tick.get("pos_y", 0.0), tick.get("pos_z", 0.0)),
            (tick.get("vel_x", 0.0), tick.get("vel_y", 0.0), tick.get("vel_z", 0.0)),
            competitors,
            threshold,
            exclude_indices=excluded,
        )
        if not hits:
            return []

        hit = hits[0]
        message = build_proximity_message(
            tick.get("player_class", ""),
            hit.driver_class,
            hit.driver_name,
            hit.side,
        )
        return [
            self._create_alert(
                message=message,
                severity="INFO",
                audio_priority=2,
                ttl=2,
                dismissable=True,
                category="proximity",
                payload={
                    "side": hit.side,
                    "distance_m": round(hit.distance_m, 2),
                    "lateral_m": round(hit.lateral_m, 2),
                    "driver_index": hit.driver_index,
                },
            )
        ]

    def _eval_safety_car(self, tick: dict) -> list[AlertMessage]:
        sc_active = tick.get("safety_car_active", False) or tick.get("full_course_yellow_active", False)
        if not sc_active:
            return []
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
            return []
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

    def _eval_fuel_critical(self, tick: dict) -> list[AlertMessage]:
        fuel_laps = tick.get("fuel_laps_remaining", tick.get("estimated_laps_remaining", 99.0))
        if fuel_laps >= 1.0:
            return []
        return [
            self._create_alert(
                message=f"¡Combustible crítico! Menos de 1 vuelta restante ({fuel_laps:.2f} laps).",
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
            },
        )
