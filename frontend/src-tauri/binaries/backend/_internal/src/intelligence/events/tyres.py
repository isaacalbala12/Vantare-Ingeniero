import uuid
from typing import Any, Dict, List

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage


# Front axle positions
FRONT = {0, 1}
# Rear axle positions
REAR = {2, 3}
# All positions
ALL = {0, 1, 2, 3}

WHEEL_NAMES = {0: "LF", 1: "RF", 2: "LR", 3: "RR"}


class TyreEvent(RaceEvent):
    """Deterministic tyre status alerts.

    Covers temperature bands, wear bands, pressures and brake lock / wheelspin.
    """

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback)
        self.cooldowns = {
            "tyre_temp_cold": 60.0,
            "tyre_temp_hot": 60.0,
            "tyre_temp_cooking": 60.0,
            "tyre_wear_knackered": 30.0,
            "tyre_wear_worn": 30.0,
            "tyre_wear_minor": 30.0,
            "tyre_wear_good": 30.0,
            "tyre_pressure_very_high": 10.0,
            "tyre_pressure_high": 10.0,
            "tyre_pressure_low": 10.0,
            "tyre_pressure_very_low": 10.0,
            "brake_lock_lap": 999_999.0,
            "brake_lock_corner": 180.0,
            "wheelspin_lap": 999_999.0,
            "wheelspin_corner": 120.0,
            "flat_spot": 999_999.0,
        }
        self._tyre_temp_notified: Dict[int, str] = {}
        self._brake_lock_lap_notified: bool = False
        self._brake_lock_corner_notified: bool = False
        self._wheelspin_lap_notified: bool = False
        self._wheelspin_corner_notified: bool = False
        self._flat_spot_notified: bool = False

    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        tyre_wear: List[float] = state.get("tyre_wear", [0.0, 0.0, 0.0, 0.0])
        tyre_temps_ico: List[float] = state.get("tyre_temps_ico", [0.0, 0.0, 0.0, 0.0])
        tyre_pressures: List[float] = state.get("tyre_pressures", [0.0, 0.0, 0.0, 0.0])
        brake_temps: List[float] = state.get("brake_temps", [0.0, 0.0, 0.0, 0.0])
        lap_number: int = int(state.get("lap_number", 0))
        sector: int = int(state.get("sector", 0))

        self._evaluate_temperatures(alerts, tyre_temps_ico)
        self._evaluate_wear(alerts, tyre_wear, sector, lap_number)
        self._evaluate_pressures(alerts, tyre_pressures)
        self._evaluate_brake_lock(alerts, brake_temps, lap_number)
        self._evaluate_flat_spot(alerts, tyre_wear)

        self.reset_tick()
        return alerts

    def _create_tyre_alert(
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
            category="tyres",
            message=message,
            audio_priority=audio_priority,
            severity=severity,
            ttl=15,
            dismissable=True,
            payload=payload or {},
        )
        self.fire(event_type, alert, min_interval)
        return alert

    def _evaluate_temperatures(
        self,
        alerts: List[AlertMessage],
        temps: List[float],
    ) -> None:
        for idx, temp in enumerate(temps):
            if temp <= 0.0:
                continue
            if temp < 60.0:
                band = "cold"
                event_type = "tyre_temp_cold"
                message = f"Neumáticos {WHEEL_NAMES[idx]} fríos ({temp:.0f} °C)."
                severity = "INFO"
                audio = "LOW"
            elif temp > 100.0:
                band = "cooking"
                event_type = "tyre_temp_cooking"
                message = f"Neumáticos {WHEEL_NAMES[idx]} se están cocinando ({temp:.0f} °C)."
                severity = "WARNING"
                audio = "HIGH"
            elif temp > 90.0:
                band = "hot"
                event_type = "tyre_temp_hot"
                message = f"Neumáticos {WHEEL_NAMES[idx]} calientes ({temp:.0f} °C)."
                severity = "INFO"
                audio = "MEDIUM"
            else:
                continue

            if self._tyre_temp_notified.get(idx) == band:
                continue
            if not self.can_fire(event_type, self.cooldowns[event_type]):
                continue

            self._create_tyre_alert(
                event_type=event_type,
                message=message,
                min_interval=self.cooldowns[event_type],
                severity=severity,
                audio_priority=audio,
                payload={"wheel_index": idx, "wheel": WHEEL_NAMES[idx], "temp_c": temp, "band": band},
            )
            self._tyre_temp_notified[idx] = band

    def _evaluate_wear(
        self,
        alerts: List[AlertMessage],
        wear: List[float],
        sector: int,
        lap_number: int,
    ) -> None:
        if sector != 2:
            return

        for idx, pct in enumerate(wear):
            if pct <= 0.0:
                continue
            if pct > 0.90:
                band = "knackered"
                event_type = "tyre_wear_knackered"
                message = f"Neumático {WHEEL_NAMES[idx]} agotado ({pct*100:.0f}%)."
                severity = "CRITICAL"
                audio = "HIGH"
            elif pct > 0.80:
                band = "worn"
                event_type = "tyre_wear_worn"
                message = f"Neumático {WHEEL_NAMES[idx]} muy desgastado ({pct*100:.0f}%)."
                severity = "WARNING"
                audio = "MEDIUM"
            elif pct > 0.60:
                band = "minor"
                event_type = "tyre_wear_minor"
                message = f"Neumático {WHEEL_NAMES[idx]} con desgaste moderado ({pct*100:.0f}%)."
                severity = "INFO"
                audio = "LOW"
            else:
                continue

            if not self.can_fire(event_type, self.cooldowns[event_type]):
                continue
            self._create_tyre_alert(
                event_type=event_type,
                message=message,
                min_interval=self.cooldowns[event_type],
                severity=severity,
                audio_priority=audio,
                payload={"wheel_index": idx, "wheel": WHEEL_NAMES[idx], "wear_pct": round(pct * 100, 1), "band": band},
            )

    def _evaluate_pressures(
        self,
        alerts: List[AlertMessage],
        pressures: List[float],
    ) -> None:
        for idx, pressure in enumerate(pressures):
            if pressure <= 0.0:
                continue
            if pressure > 30.0:
                band = "very_high"
                event_type = "tyre_pressure_very_high"
                message = f"Presión {WHEEL_NAMES[idx]} muy alta ({pressure:.1f} psi)."
                severity = "WARNING"
                audio = "MEDIUM"
            elif pressure > 25.0:
                band = "high"
                event_type = "tyre_pressure_high"
                message = f"Presión {WHEEL_NAMES[idx]} alta ({pressure:.1f} psi)."
                severity = "INFO"
                audio = "LOW"
            elif pressure < 18.0:
                band = "very_low"
                event_type = "tyre_pressure_very_low"
                message = f"Presión {WHEEL_NAMES[idx]} muy baja ({pressure:.1f} psi)."
                severity = "CRITICAL"
                audio = "HIGH"
            elif pressure < 21.0:
                band = "low"
                event_type = "tyre_pressure_low"
                message = f"Presión {WHEEL_NAMES[idx]} baja ({pressure:.1f} psi)."
                severity = "WARNING"
                audio = "MEDIUM"
            else:
                continue

            if not self.can_fire(event_type, self.cooldowns[event_type]):
                continue
            self._create_tyre_alert(
                event_type=event_type,
                message=message,
                min_interval=self.cooldowns[event_type],
                severity=severity,
                audio_priority=audio,
                payload={"wheel_index": idx, "wheel": WHEEL_NAMES[idx], "pressure_psi": pressure, "band": band},
            )

    def _evaluate_brake_lock(
        self,
        alerts: List[AlertMessage],
        brake_temps: List[float],
        lap_number: int,
    ) -> None:
        # Brake lock lap: front temps significantly higher than rears
        if len(brake_temps) < 4:
            return
        front_avg = (brake_temps[0] + brake_temps[1]) / 2.0
        rear_avg = (brake_temps[2] + brake_temps[3]) / 2.0
        if front_avg <= 0.0 or rear_avg <= 0.0:
            return
        if front_avg < rear_avg * 1.25:
            return

        event_type = "brake_lock_lap"
        if self._brake_lock_lap_notified:
            return
        if not self.can_fire(event_type, self.cooldowns[event_type]):
            return

        self._create_tyre_alert(
            event_type=event_type,
            message=f"Posibles bloqueos de frenos delanteros en la vuelta {lap_number}.",
            min_interval=self.cooldowns[event_type],
            severity="WARNING",
            audio_priority="MEDIUM",
            payload={"lap_number": lap_number, "front_brake_temp_avg": round(front_avg, 1)},
        )
        self._brake_lock_lap_notified = True

    def _evaluate_flat_spot(
        self,
        alerts: List[AlertMessage],
        wear: List[float],
    ) -> None:
        if self._flat_spot_notified:
            return
        if len(wear) < 4:
            return
        front_avg = (wear[0] + wear[1]) / 2.0
        if front_avg < 0.50:
            return
        if not self.can_fire("flat_spot", self.cooldowns["flat_spot"]):
            return

        self._create_tyre_alert(
            event_type="flat_spot",
            message="Posible flat spot en neumáticos delanteros.",
            min_interval=self.cooldowns["flat_spot"],
            severity="WARNING",
            audio_priority="MEDIUM",
            payload={"front_avg_wear_pct": round(front_avg * 100, 1)},
        )
        self._flat_spot_notified = True
