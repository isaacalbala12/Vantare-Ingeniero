import math
import time
import uuid
from typing import Any, Dict, List

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage


class DamageEvent(RaceEvent):
    """Deterministic damage and collision alerts.

    Triggers include high-G impacts, punctures, component damage, and rollover.
    """

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback)
        self.cooldowns = {
            "collision_high_g": 3.0,
            "puncture": 5.0,
            "damage_engine": 300.0,
            "damage_transmission": 300.0,
            "damage_aero": 300.0,
            "damage_suspension": 300.0,
            "damage_brakes": 300.0,
            "wheel_missing": 5.0,
            "car_rolling": 300.0,
            "car_upside_down": 999_999.0,
        }
        self._collision_settle_start: float = 0.0
        self._settled: bool = True
        self._last_impact_g: float = 0.0
        self._orientation_warned: bool = False

    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        now = time.time()
        speed_mps: float = float(state.get("speed", 0.0))
        roll: float = float(state.get("roll", 0.0))
        pitch: float = float(state.get("pitch", 0.0))
        tyre_pressures: List[float] = state.get("tyre_pressures", [0.0, 0.0, 0.0, 0.0])
        impact_g: float = float(state.get("impact_g", 0.0))
        engine_damage: float = float(state.get("engine_damage", 0.0))
        transmission_damage: float = float(state.get("transmission_damage", 0.0))
        aero_damage: float = float(state.get("aero_damage", 0.0))
        suspension_damage: float = float(state.get("suspension_damage", 0.0))
        brake_damage: float = float(state.get("brake_damage", 0.0))
        wheel_missing: List[bool] = state.get("wheel_missing", [False, False, False, False])

        self._evaluate_collision(alerts, impact_g, speed_mps)
        self._evaluate_puncture(alerts, tyre_pressures)
        self._evaluate_component_damage(alerts, engine_damage, "engine", "damage_engine")
        self._evaluate_component_damage(alerts, transmission_damage, "transmission", "damage_transmission")
        self._evaluate_component_damage(alerts, aero_damage, "aero", "damage_aero")
        self._evaluate_component_damage(alerts, suspension_damage, "suspension", "damage_suspension")
        self._evaluate_component_damage(alerts, brake_damage, "brakes", "damage_brakes")
        self._evaluate_wheel_missing(alerts, wheel_missing)
        self._evaluate_orientation(alerts, roll, pitch, speed_mps)

        self.reset_tick()
        return alerts

    def _create_damage_alert(
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
            category="damage",
            message=message,
            audio_priority=audio_priority,
            severity=severity,
            ttl=15,
            dismissable=True,
            payload=payload or {},
        )
        self.fire(event_type, alert, min_interval)
        return alert

    def _evaluate_collision(
        self,
        alerts: List[AlertMessage],
        impact_g: float,
        speed_mps: float,
    ) -> None:
        if impact_g <= 40.0:
            self._settled = True
            return
        if not self._settled:
            if time.time() - self._collision_settle_start < 3.0:
                return
            self._settled = True
        self._settled = False
        self._collision_settle_start = time.time()
        self._last_impact_g = impact_g

        severity = "CRITICAL" if impact_g > 80.0 else "WARNING"
        audio = "CRITICAL" if severity == "CRITICAL" else "HIGH"
        self._create_damage_alert(
            event_type="collision_high_g",
            message=f"Colisión intensa detectada ({impact_g:.0f} G). ¿Estás bien?",
            min_interval=self.cooldowns["collision_high_g"],
            severity=severity,
            audio_priority=audio,
            payload={"impact_g": impact_g, "speed_mps": speed_mps},
        )

    def _evaluate_puncture(
        self,
        alerts: List[AlertMessage],
        pressures: List[float],
    ) -> None:
        for idx, pressure in enumerate(pressures):
            if pressure <= 0.0:
                continue
            if pressure >= 30.0:
                continue
            if not self.can_fire("puncture", self.cooldowns["puncture"]):
                continue
            wheel = WHEEL_NAMES[idx]
            self._create_damage_alert(
                event_type="puncture",
                message=f"Posible pinchazo en {wheel} ({pressure:.1f} psi).",
                min_interval=self.cooldowns["puncture"],
                severity="CRITICAL",
                audio_priority="CRITICAL",
                payload={"wheel_index": idx, "wheel": wheel, "pressure_psi": pressure},
            )

    def _evaluate_component_damage(
        self,
        alerts: List[AlertMessage],
        damage_value: float,
        component: str,
        event_type: str,
    ) -> None:
        if damage_value <= 0.0:
            return
        if not self.can_fire(event_type, self.cooldowns[event_type]):
            return
        if damage_value >= 0.7:
            severity = "CRITICAL"
            audio = "CRITICAL"
            message = f"Daño severo en {component}."
        elif damage_value >= 0.3:
            severity = "WARNING"
            audio = "HIGH"
            message = f"Daño moderado en {component}."
        else:
            severity = "INFO"
            audio = "MEDIUM"
            message = f"Daño leve en {component}."
        self._create_damage_alert(
            event_type=event_type,
            message=message,
            min_interval=self.cooldowns[event_type],
            severity=severity,
            audio_priority=audio,
            payload={"component": component, "damage": round(damage_value, 3)},
        )

    def _evaluate_wheel_missing(
        self,
        alerts: List[AlertMessage],
        wheel_missing: List[bool],
    ) -> None:
        if len(wheel_missing) < 4:
            return
        for idx, missing in enumerate(wheel_missing):
            if not missing:
                continue
            if not self.can_fire("wheel_missing", self.cooldowns["wheel_missing"]):
                continue
            self._create_damage_alert(
                event_type="wheel_missing",
                message=f"Rueda {WHEEL_NAMES[idx]} perdida.",
                min_interval=self.cooldowns["wheel_missing"],
                severity="CRITICAL",
                audio_priority="CRITICAL",
                payload={"wheel_index": idx, "wheel": WHEEL_NAMES[idx]},
            )

    def _evaluate_orientation(
        self,
        alerts: List[AlertMessage],
        roll: float,
        pitch: float,
        speed_mps: float,
    ) -> None:
        threshold_rad = 1.7
        is_upside_down = abs(roll) > threshold_rad or abs(pitch) > threshold_rad
        if not is_upside_down:
            self._orientation_warned = False
            return

        if speed_mps > 2.0:
            if not self.can_fire("car_rolling", self.cooldowns["car_rolling"]):
                return
            self._create_damage_alert(
                event_type="car_rolling",
                message="¡El coche está volcando!",
                min_interval=self.cooldowns["car_rolling"],
                severity="CRITICAL",
                audio_priority="CRITICAL",
                payload={"roll": round(roll, 3), "pitch": round(pitch, 3)},
            )
        else:
            if self._orientation_warned:
                return
            if not self.can_fire("car_upside_down", self.cooldowns["car_upside_down"]):
                return
            self._create_damage_alert(
                event_type="car_upside_down",
                message="El coche está boca abajo.",
                min_interval=self.cooldowns["car_upside_down"],
                severity="CRITICAL",
                audio_priority="CRITICAL",
                payload={"roll": round(roll, 3), "pitch": round(pitch, 3)},
            )
            self._orientation_warned = True


WHEEL_NAMES = {0: "LF", 1: "RF", 2: "LR", 3: "RR"}
