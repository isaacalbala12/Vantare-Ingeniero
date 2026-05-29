from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage

logger = logging.getLogger("vantare.race_time")


class RaceTimeEvent(RaceEvent):
    """Eventos de tiempo restante de carrera.

    Flags de cooldown por sesión (se resetean con reset_session).
    """

    def __init__(self, broadcast_callback=None, **kwargs: Any) -> None:
        super().__init__(broadcast_callback=broadcast_callback)
        self._cooldowns: Dict[str, float] = {
            "20mins": 0.0,
            "15mins": 0.0,
            "10mins": 0.0,
            "5mins": 0.0,
            "2mins": 0.0,
            "0mins": 0.0,
            "halfway": 0.0,
            "last_lap": 0.0,
        }
        self._last_session_laps_left: float = 0.0
        self._last_session_time_left: float = 0.0

    # ------------------------------------------------------------------ #
    # Helpers públicos
    # ------------------------------------------------------------------ #
    def reset_session(self) -> None:
        self._last_fired.clear()
        self._fired_in_tick.clear()
        self._cooldowns = {
            "20mins": 0.0,
            "15mins": 0.0,
            "10mins": 0.0,
            "5mins": 0.0,
            "2mins": 0.0,
            "0mins": 0.0,
            "halfway": 0.0,
            "last_lap": 0.0,
        }
        self._last_session_laps_left = 0.0
        self._last_session_time_left = 0.0

    # ------------------------------------------------------------------ #
    # evaluate
    # ------------------------------------------------------------------ #
    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        self.reset_tick()

        if not state:
            return alerts

        session_type: str = str(state.get("session_type", "race")).lower()
        if session_type not in ("race", "race", "r"):
            # Solo eventos de tiempo de carrera
            return alerts

        session_time_left: float = float(state.get("session_time_left", 0.0) or 0.0)
        session_laps_left: float = float(state.get("session_laps_left", 0.0) or 0.0)
        is_last_lap: bool = bool(state.get("is_last_lap", False))
        position: int = int(state.get("class_position", 0) or 0)

        # Cambio de sesión detectado por salto grande en tiempo restante
        if (
            self._last_session_time_left > 0
            and session_time_left > self._last_session_time_left + 60.0
        ):
            self.reset_session()

        self._last_session_time_left = session_time_left
        self._last_session_laps_left = session_laps_left

        minutes_left = session_time_left / 60.0

        # 1. Countdown de minutos
        self._evaluate_minute_countdown(minutes_left, position, alerts)

        # 2. Halfway
        self._evaluate_halfway(session_time_left, alerts)

        # 3. Last lap
        self._evaluate_last_lap(is_last_lap, position, session_laps_left, alerts)

        return alerts

    # ------------------------------------------------------------------ #
    # Countdown de minutos
    # ------------------------------------------------------------------ #
    def _evaluate_minute_countdown(self, minutes_left: float, position: int, alerts: List[AlertMessage]) -> None:
        # 20 mins
        if 19.9 < minutes_left < 20.1 and self.can_fire("20mins", self._cooldowns.get("20mins", 0.0)):
            self._cooldowns["20mins"] = 30.0
            alerts.append(self._create_alert("Quedan 20 minutos de carrera.", "INFO", 1, 8, True, "race_time", {}))

        # 15 mins
        if 14.9 < minutes_left < 15.1 and self.can_fire("15mins", self._cooldowns.get("15mins", 0.0)):
            self._cooldowns["15mins"] = 30.0
            alerts.append(self._create_alert("Quedan 15 minutos de carrera.", "INFO", 1, 8, True, "race_time", {}))

        # 10 mins
        if 9.9 < minutes_left < 10.1 and self.can_fire("10mins", self._cooldowns.get("10mins", 0.0)):
            self._cooldowns["10mins"] = 30.0
            alerts.append(self._create_alert("Quedan 10 minutos de carrera.", "INFO", 1, 8, True, "race_time", {}))

        # 5 mins (variantes)
        if 4.9 < minutes_left < 5.1 and self.can_fire("5mins", self._cooldowns.get("5mins", 0.0)):
            self._cooldowns["5mins"] = 30.0
            if position == 1:
                alerts.append(self._create_alert(
                    "¡Quedan 5 minutos y lideras la carrera!",
                    "HIGH", 2, 10, True, "race_time", {"position": position}
                ))
            elif 1 < position < 4:
                alerts.append(self._create_alert(
                    f"Quedan 5 minutos. Posición {position}, en el podio.",
                    "HIGH", 2, 10, True, "race_time", {"position": position}
                ))
            else:
                alerts.append(self._create_alert(
                    "Quedan 5 minutos de carrera.",
                    "INFO", 1, 8, True, "race_time", {"position": position}
                ))

        # 2 mins
        if 1.9 < minutes_left < 2.1 and self.can_fire("2mins", self._cooldowns.get("2mins", 0.0)):
            self._cooldowns["2mins"] = 20.0
            alerts.append(self._create_alert("Quedan 2 minutos de carrera.", "HIGH", 2, 10, True, "race_time", {}))

        # 0 mins / bandera a cuadros
        if minutes_left <= 0.2 and self.can_fire("0mins", self._cooldowns.get("0mins", 0.0)):
            self._cooldowns["0mins"] = 60.0
            alerts.append(self._create_alert(
                "¡Tiempo cumplido! Bandera a cuadros.",
                "CRITICAL", 3, 15, True, "race_time", {"position": position}
            ))

    # ------------------------------------------------------------------ #
    # Halfway
    # ------------------------------------------------------------------ #
    def _evaluate_halfway(self, session_time_left: float, alerts: List[AlertMessage]) -> None:
        if session_time_left <= 0:
            return
        half = getattr(self, "_session_halftime", None)
        if half is None:
            return
        if session_time_left < half and self.can_fire("halfway", self._cooldowns.get("halfway", 0.0)):
            self._cooldowns["halfway"] = 120.0
            alerts.append(self._create_alert(
                "Mitad de carrera alcanzada.",
                "HIGH", 2, 10, True, "race_time", {}
            ))

    def set_halftime(self, session_time_left: float) -> None:
        """Configura el punto de mitad de carrera (tiempo total / 2)."""
        if session_time_left > 0:
            self._session_halftime = session_time_left / 2.0

    # ------------------------------------------------------------------ #
    # Last lap
    # ------------------------------------------------------------------ #
    def _evaluate_last_lap(
        self,
        is_last_lap: bool,
        position: int,
        session_laps_left: float,
        alerts: List[AlertMessage],
    ) -> None:
        if not is_last_lap and session_laps_left > 1:
            return
        if self.can_fire("last_lap", self._cooldowns.get("last_lap", 0.0)):
            self._cooldowns["last_lap"] = 30.0
            if position == 1:
                alerts.append(self._create_alert(
                    "¡Última vuelta y lideras!",
                    "CRITICAL", 4, 15, True, "race_time", {"position": position}
                ))
            elif 1 < position < 4:
                alerts.append(self._create_alert(
                    f"Última vuelta. Posición {position}, en el podio.",
                    "HIGH", 2, 10, True, "race_time", {"position": position}
                ))
            else:
                alerts.append(self._create_alert(
                    "Última vuelta de carrera.",
                    "HIGH", 2, 10, True, "race_time", {"position": position}
                ))

    # ------------------------------------------------------------------ #
    # Alert factory
    # ------------------------------------------------------------------ #
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
            alert_id=str(__import__("uuid").uuid4()),
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
