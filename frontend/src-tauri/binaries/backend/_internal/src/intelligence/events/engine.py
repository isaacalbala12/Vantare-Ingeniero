import uuid
from typing import Any, Dict, List

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage


class EngineEvent(RaceEvent):
    """Deterministic engine / powertrain status alerts.

    Implements temperature, pressure and stall detection from the reference.
    """

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback)
        self.cooldowns = {
            "engine_water_temp_high": 60.0,
            "engine_oil_temp_high": 60.0,
            "engine_oil_pressure_low": 120.0,
            "engine_fuel_pressure_low": 120.0,
            "engine_stalled": 120.0,
            "engine_all_clear": 120.0,
        }
        self._water_high: bool = False
        self._oil_high: bool = False
        self._oil_pressure_low: bool = False
        self._fuel_pressure_low: bool = False
        self._stalled: bool = False
        self._all_clear: bool = True

    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        water_temp: float = float(state.get("water_temp", 0.0))
        oil_temp: float = float(state.get("oil_temp", 0.0))
        oil_pressure: float = float(state.get("oil_pressure", 0.0))
        fuel_pressure: float = float(state.get("fuel_pressure", 0.0))
        engine_stalled: bool = bool(state.get("engine_stalled", False))
        max_safe_water_temp: float = float(state.get("max_safe_water_temp", 105.0))
        max_safe_oil_temp: float = float(state.get("max_safe_oil_temp", 140.0))
        speed_mps: float = float(state.get("speed", 0.0))

        self._evaluate_water_temp(alerts, water_temp, max_safe_water_temp)
        self._evaluate_oil_temp(alerts, oil_temp, max_safe_oil_temp)
        self._evaluate_oil_pressure(alerts, oil_pressure)
        self._evaluate_fuel_pressure(alerts, fuel_pressure)
        self._evaluate_stall(alerts, engine_stalled, speed_mps)
        self._evaluate_all_clear(
            alerts, water_temp, max_safe_water_temp, oil_temp, max_safe_oil_temp,
            oil_pressure, fuel_pressure, engine_stalled,
        )

        self.reset_tick()
        return alerts

    def _create_engine_alert(
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
            category="engine",
            message=message,
            audio_priority=audio_priority,
            severity=severity,
            ttl=15,
            dismissable=True,
            payload=payload or {},
        )
        self.fire(event_type, alert, min_interval)
        return alert

    def _evaluate_water_temp(
        self,
        alerts: List[AlertMessage],
        water_temp: float,
        max_safe: float,
    ) -> None:
        if water_temp <= 0.0:
            return
        if water_temp <= max_safe:
            self._water_high = False
            return
        if self._water_high:
            return
        if not self.can_fire("engine_water_temp_high", self.cooldowns["engine_water_temp_high"]):
            return

        self._create_engine_alert(
            event_type="engine_water_temp_high",
            message=f"Temperatura del agua elevada ({water_temp:.0f} °C).",
            min_interval=self.cooldowns["engine_water_temp_high"],
            severity="WARNING",
            audio_priority="HIGH",
            payload={"water_temp_c": water_temp, "max_safe_water_temp_c": max_safe},
        )
        self._water_high = True

    def _evaluate_oil_temp(
        self,
        alerts: List[AlertMessage],
        oil_temp: float,
        max_safe: float,
    ) -> None:
        if oil_temp <= 0.0:
            return
        if oil_temp <= max_safe:
            self._oil_high = False
            return
        if self._oil_high:
            return
        if not self.can_fire("engine_oil_temp_high", self.cooldowns["engine_oil_temp_high"]):
            return

        self._create_engine_alert(
            event_type="engine_oil_temp_high",
            message=f"Temperatura del aceite elevada ({oil_temp:.0f} °C).",
            min_interval=self.cooldowns["engine_oil_temp_high"],
            severity="WARNING",
            audio_priority="HIGH",
            payload={"oil_temp_c": oil_temp, "max_safe_oil_temp_c": max_safe},
        )
        self._oil_high = True

    def _evaluate_oil_pressure(
        self,
        alerts: List[AlertMessage],
        oil_pressure: float,
    ) -> None:
        # Warning assumed when below a safe threshold; reference uses a boolean flag.
        # Here we derive from a common minimum (~1.0 bar / ~15 psi).
        safe_oil_pressure: float = float(state.get("min_safe_oil_pressure", 1.0)) if "state" in dir() else 1.0
        # Not using state-derived threshold here to keep interface simple.
        threshold = 1.0
        if oil_pressure >= threshold or oil_pressure <= 0.0:
            self._oil_pressure_low = False
            return
        if self._oil_pressure_low:
            return
        if not self.can_fire("engine_oil_pressure_low", self.cooldowns["engine_oil_pressure_low"]):
            return

        self._create_engine_alert(
            event_type="engine_oil_pressure_low",
            message="Presión de aceite baja.",
            min_interval=self.cooldowns["engine_oil_pressure_low"],
            severity="CRITICAL",
            audio_priority="CRITICAL",
            payload={"oil_pressure_bar": oil_pressure},
        )
        self._oil_pressure_low = True

    def _evaluate_fuel_pressure(
        self,
        alerts: List[AlertMessage],
        fuel_pressure: float,
    ) -> None:
        threshold = 1.5
        if fuel_pressure >= threshold or fuel_pressure <= 0.0:
            self._fuel_pressure_low = False
            return
        if self._fuel_pressure_low:
            return
        if not self.can_fire("engine_fuel_pressure_low", self.cooldowns["engine_fuel_pressure_low"]):
            return

        self._create_engine_alert(
            event_type="engine_fuel_pressure_low",
            message="Presión de combustible baja.",
            min_interval=self.cooldowns["engine_fuel_pressure_low"],
            severity="WARNING",
            audio_priority="HIGH",
            payload={"fuel_pressure_bar": fuel_pressure},
        )
        self._fuel_pressure_low = True

    def _evaluate_stall(
        self,
        alerts: List[AlertMessage],
        engine_stalled: bool,
        speed_mps: float,
    ) -> None:
        if not engine_stalled or speed_mps > 5.0:
            self._stalled = False
            return
        if self._stalled:
            return
        if not self.can_fire("engine_stalled", self.cooldowns["engine_stalled"]):
            return

        self._create_engine_alert(
            event_type="engine_stalled",
            message="Motor calado.",
            min_interval=self.cooldowns["engine_stalled"],
            severity="CRITICAL",
            audio_priority="CRITICAL",
            payload={"speed_mps": speed_mps},
        )
        self._stalled = True

    def _evaluate_all_clear(
        self,
        alerts: List[AlertMessage],
        water_temp: float,
        max_safe_water: float,
        oil_temp: float,
        max_safe_oil: float,
        oil_pressure: float,
        fuel_pressure: float,
        engine_stalled: bool,
    ) -> None:
        problems = (
            (water_temp > max_safe_water and water_temp > 0.0)
            or (oil_temp > max_safe_oil and oil_temp > 0.0)
            or (oil_pressure < 1.0 and oil_pressure > 0.0)
            or (fuel_pressure < 1.5 and fuel_pressure > 0.0)
            or engine_stalled
        )
        if problems:
            self._all_clear = False
            return
        if self._all_clear:
            return
        if not self.can_fire("engine_all_clear", self.cooldowns["engine_all_clear"]):
            return

        self._create_engine_alert(
            event_type="engine_all_clear",
            message="Motor: todo en orden.",
            min_interval=self.cooldowns["engine_all_clear"],
            severity="INFO",
            audio_priority="LOW",
            payload={},
        )
        self._all_clear = True
