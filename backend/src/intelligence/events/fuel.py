import time
import uuid
from typing import Any, Dict, List

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage


class FuelEvent(RaceEvent):
    """Deterministic fuel monitoring alerts.

    Implements the reference behaviour from the Crew Chief `Fuel.cs` triggers.
    """

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback)
        self.cooldowns = {
            "fuel_check": 5.0,
            "estimate_1_lap": 30.0,
            "estimate_2_laps": 30.0,
            "estimate_3_laps": 30.0,
            "estimate_4_laps": 30.0,
            "half_distance_good": 999_999.0,
            "half_distance_low": 999_999.0,
            "half_tank_warning": 999_999.0,
            "pit_now_for_fuel": 999_999.0,
            "about_to_run_out": 30.0,
            "one_litre_remaining": 999_999.0,
        }
        self._half_distance_notified: bool = False
        self._half_tank_notified: bool = False
        self._pit_now_notified: bool = False
        self._one_litre_notified: bool = False

    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []

        fuel_remaining: float = float(state.get("fuel_remaining", 0.0))
        fuel_capacity: float = float(state.get("fuel_capacity", 0.0))
        fuel_per_lap: float = float(state.get("fuel_per_lap", 0.0))
        completed_laps: int = int(state.get("completed_laps", 0))
        is_race: bool = bool(state.get("is_race", True))

        if fuel_capacity <= 0.0 or fuel_per_lap <= 0.0:
            return alerts

        laps_remaining: float = fuel_remaining / fuel_per_lap
        half_distance: int = max(1, int(state.get("total_laps", 0) / 2))
        reserve_laps: float = 2.0  # ~half lap reserve (2L as per reference)

        if is_race:
            self._evaluate_estimates(alerts, laps_remaining, fuel_remaining)
            self._evaluate_half_distance(
                alerts, completed_laps, half_distance, fuel_remaining, fuel_capacity
            )
            self._evaluate_half_tank(alerts, fuel_remaining, fuel_capacity)
            self._evaluate_pit_now(alerts, laps_remaining, reserve_laps)
            self._evaluate_critical(alerts, laps_remaining, fuel_remaining)

        self.reset_tick()
        return alerts

    def _create_fuel_alert(
        self,
        event_type: str,
        message: str,
        min_interval: float = 5.0,
        severity: str = "WARNING",
        audio_priority: str = "MEDIUM",
        payload: Dict[str, Any] | None = None,
    ) -> AlertMessage:
        alert = AlertMessage(
            event=event_type,
            alert_id=str(uuid.uuid4()),
            category="fuel",
            message=message,
            audio_priority=audio_priority,
            severity=severity,
            ttl=15,
            dismissable=True,
            payload=payload or {},
        )
        self.fire(event_type, alert, min_interval)
        return alert

    def _evaluate_estimates(
        self, alerts: List[AlertMessage], laps_remaining: float, fuel_remaining: float
    ) -> None:
        if laps_remaining >= 1.0 and self.can_fire("fuel_check", self.cooldowns["fuel_check"]):
            self._fired_in_tick.add("fuel_check")
            self._last_fired["fuel_check"] = time.time()

        rounded = int(laps_remaining + 0.999)
        if rounded < 1:
            rounded = 1

        mapping = {
            1: ("estimate_1_lap", f"Combustible estimado: {rounded} vuelta restante.", "HIGH", "HIGH"),
            2: ("estimate_2_laps", f"Combustible estimado: {rounded} vueltas restantes.", "MEDIUM", "MEDIUM"),
            3: ("estimate_3_laps", f"Combustible estimado: {rounded} vueltas restantes.", "MEDIUM", "MEDIUM"),
            4: ("estimate_4_laps", f"Combustible estimado: {rounded} vueltas restantes.", "LOW", "LOW"),
        }
        if 1 <= rounded <= 4:
            event_type, message, severity, audio = mapping[rounded]
            if self.can_fire(event_type, self.cooldowns[event_type]):
                self._create_fuel_alert(
                    event_type=event_type,
                    message=message,
                    min_interval=self.cooldowns[event_type],
                    severity=severity,
                    audio_priority=audio,
                    payload={"laps_remaining": laps_remaining, "fuel_remaining_litres": fuel_remaining},
                )

    def _evaluate_half_distance(
        self,
        alerts: List[AlertMessage],
        completed_laps: int,
        half_distance: int,
        fuel_remaining: float,
        fuel_capacity: float,
    ) -> None:
        if completed_laps != half_distance:
            return
        if self._half_distance_notified:
            return

        fuel_percentage = (fuel_remaining / fuel_capacity * 100.0) if fuel_capacity > 0.0 else 0.0
        if fuel_percentage >= 45.0:
            event_type = "half_distance_good"
            message = "Media distancia. Combustible suficiente para completar la carrera."
            severity = "INFO"
        else:
            event_type = "half_distance_low"
            message = "Media distancia. Combustible bajo, planifica tu próxima parada."
            severity = "WARNING"

        self._create_fuel_alert(
            event_type=event_type,
            message=message,
            min_interval=self.cooldowns[event_type],
            severity=severity,
            audio_priority="MEDIUM",
            payload={
                "completed_laps": completed_laps,
                "half_distance": half_distance,
                "fuel_percentage": round(fuel_percentage, 1),
            },
        )
        self._half_distance_notified = True

    def _evaluate_half_tank(
        self,
        alerts: List[AlertMessage],
        fuel_remaining: float,
        fuel_capacity: float,
    ) -> None:
        if self._half_tank_notified:
            return
        if fuel_remaining >= fuel_capacity / 2.0:
            return

        self._create_fuel_alert(
            event_type="half_tank_warning",
            message="Medio tanque de combustible.",
            min_interval=self.cooldowns["half_tank_warning"],
            severity="INFO",
            audio_priority="LOW",
            payload={"fuel_remaining_litres": fuel_remaining, "fuel_capacity_litres": fuel_capacity},
        )
        self._half_tank_notified = True

    def _evaluate_pit_now(
        self,
        alerts: List[AlertMessage],
        laps_remaining: float,
        reserve_laps: float,
    ) -> None:
        if self._pit_now_notified:
            return
        if laps_remaining > reserve_laps:
            return

        self._create_fuel_alert(
            event_type="pit_now_for_fuel",
            message="Combustible crítico. Entra a boxes esta vuelta.",
            min_interval=self.cooldowns["pit_now_for_fuel"],
            severity="CRITICAL",
            audio_priority="CRITICAL",
            payload={"laps_remaining": laps_remaining, "reserve_laps": reserve_laps},
        )
        self._pit_now_notified = True

    def _evaluate_critical(
        self,
        alerts: List[AlertMessage],
        laps_remaining: float,
        fuel_remaining: float,
    ) -> None:
        if fuel_remaining < 2.0:
            event_type = "about_to_run_out" if fuel_remaining >= 1.0 else "one_litre_remaining"
            min_interval = self.cooldowns[event_type]
            if fuel_remaining < 1.0 and self._one_litre_notified:
                return
            if fuel_remaining >= 1.0 and not self.can_fire(event_type, min_interval):
                return

            message = (
                "¡Queda menos de un litro de combustible!"
                if event_type == "one_litre_remaining"
                else f"¡A punto de quedarte sin combustible! {fuel_remaining:.2f} litros restantes."
            )
            self._create_fuel_alert(
                event_type=event_type,
                message=message,
                min_interval=min_interval,
                severity="CRITICAL",
                audio_priority="CRITICAL",
                payload={"fuel_remaining_litres": fuel_remaining},
            )
            if event_type == "one_litre_remaining":
                self._one_litre_notified = True
