from __future__ import annotations

import logging
import random
import time
import uuid
from typing import Any, Dict, List, Optional

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage

logger = logging.getLogger("vantare.position")


class PositionEvent(RaceEvent):
    """Eventos de posición, adelantamientos y salidas.

    Parámetros (sobrescribibles por subclase):
        passCheckInterval: float = 1.0
        minTimeBetweenOvertakeMessages: float = 20.0
        minTimeToWait: float = 4.0
        maxTimeToWait: float = 7.0
        positionReminderMinLap: int = 2
        positionReminderMaxLap: int = 4
    """

    def __init__(self, broadcast_callback=None, **kwargs: Any) -> None:
        super().__init__(broadcast_callback=broadcast_callback)
        self.pass_check_interval: float = kwargs.get("passCheckInterval", 1.0)
        self.min_time_between_overtake_messages: float = kwargs.get("minTimeBetweenOvertakeMessages", 20.0)
        self.min_time_to_wait: float = kwargs.get("minTimeToWait", 4.0)
        self.max_time_to_wait: float = kwargs.get("maxTimeToWait", 7.0)
        self.position_reminder_min_lap: int = kwargs.get("positionReminderMinLap", 2)
        self.position_reminder_max_lap: int = kwargs.get("positionReminderMaxLap", 4)

        # Estado interno para detección de adelantamientos
        self._last_pass_check: float = 0.0
        self._last_pass_alert_time: float = 0.0
        self._pending_pass: Optional[Dict[str, Any]] = None
        self._pending_behind: Optional[Dict[str, Any]] = None
        self._current_session_start_position: Optional[int] = None
        self._start_quality_fired: bool = False
        self._expected_finish_fired: bool = False
        self._position_reminder_scheduled_lap: Optional[int] = None
        self._position_reminder_fired: bool = False
        self._last_lap_number: int = 0
        self._last_position: int = 0
        self._last_is_new_lap: bool = False
        self._gap_samples_ahead: List[float] = []
        self._gap_samples_behind: List[float] = []
        self._current_overtake_opponent: Optional[int] = None
        self._current_behind_opponent: Optional[int] = None
        self._cooldowns: Dict[str, float] = {
            "position": 0.0,
            "overtake": 0.0,
            "behind_overtake": 0.0,
            "start_quality": 0.0,
            "expected_finish": 0.0,
            "position_reminder": 0.0,
        }

    # ------------------------------------------------------------------ #
    # Helpers públicos
    # ------------------------------------------------------------------ #
    def reset_session(self) -> None:
        """Resetea el estado al cambiar de sesión."""
        self._last_fired.clear()
        self._fired_in_tick.clear()
        self._last_pass_check = 0.0
        self._last_pass_alert_time = 0.0
        self._pending_pass = None
        self._pending_behind = None
        self._current_session_start_position = None
        self._start_quality_fired = False
        self._expected_finish_fired = False
        self._position_reminder_scheduled_lap = None
        self._position_reminder_fired = False
        self._last_lap_number = 0
        self._last_position = 0
        self._last_is_new_lap = False
        self._gap_samples_ahead = []
        self._gap_samples_behind = []
        self._current_overtake_opponent = None
        self._current_behind_opponent = None
        self._cooldowns = {
            "position": 0.0,
            "overtake": 0.0,
            "behind_overtake": 0.0,
            "start_quality": 0.0,
            "expected_finish": 0.0,
            "position_reminder": 0.0,
        }

    # ------------------------------------------------------------------ #
    # evaluate
    # ------------------------------------------------------------------ #
    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        self.reset_tick()

        if not state:
            return alerts

        lap_number: int = int(state.get("lap_number", 0) or 0)
        session_laps_left: float = float(state.get("session_laps_left", 0.0) or 0.0)
        is_new_lap: bool = bool(state.get("is_new_lap", False))
        position: int = int(state.get("class_position", 0) or 0)
        session_type: str = str(state.get("session_type", "race")).lower()

        # Detectar inicio de sesión (vuelta 0 -> 1)
        if lap_number == 1 and self._last_lap_number == 0:
            self._current_session_start_position = position
            self._start_quality_fired = False
            self._expected_finish_fired = False
            self._position_reminder_scheduled_lap = random.randint(
                self.position_reminder_min_lap, self.position_reminder_max_lap
            )
            self._position_reminder_fired = False

        # Inicializar última posición en la primera vuelta
        if self._last_lap_number == 0 and lap_number > 0 and self._last_position == 0:
            self._last_position = position
            self._last_lap_number = lap_number

        # 1. Posición actual en nueva vuelta
        if is_new_lap and self._last_lap_number != lap_number:
            if position > 0 and position != self._last_position:
                if self.can_fire("position", self._cooldowns.get("position", 0.0)):
                    self._cooldowns["position"] = 10.0
                    alerts.append(self._create_position_alert(position))
            self._last_position = position
            self._last_lap_number = lap_number

            # Posición de salida
            self._evaluate_start_quality(state, alerts)

        # 2. Recordatorio de posición
        self._evaluate_position_reminder(state, lap_number, alerts)

        # 3. Expected finish (solo al empezar carrera)
        if session_type == "race" and lap_number == 1 and not self._expected_finish_fired:
            self._expected_finish_fired = True
            if self._current_session_start_position:
                alerts.append(self._create_expected_finish_alert(self._current_session_start_position))

        # 4. Adelantamientos / ser adelantado (muestreo cada 1s)
        self._evaluate_overtakes(state, alerts)

        self._last_is_new_lap = is_new_lap
        return alerts

    # ------------------------------------------------------------------ #
    # Helpers privados
    # ------------------------------------------------------------------ #
    def _evaluate_start_quality(self, state: Dict[str, Any], alerts: List[AlertMessage]) -> None:
        if self._start_quality_fired:
            return
        if self._current_session_start_position is None:
            return
        position = int(state.get("class_position", 0) or 0)
        if position <= 0:
            return

        start_pos = self._current_session_start_position
        delta = position - start_pos

        severity = "INFO"
        audio_priority = 1
        ttl = 8
        message = ""
        event_type = "start_quality"

        if delta <= -1 or position == 1:
            message = f"¡Buena salida! Posición {position} (mejoraste {abs(delta)} posiciones)."
            severity = "HIGH"
            audio_priority = 2
            ttl = 10
            event_type = "start_quality_good"
        elif delta <= 0:
            message = f"Salida correcta. Posición {position}."
            severity = "INFO"
            audio_priority = 1
            ttl = 5
            event_type = "start_quality_ok"
        elif delta >= 5:
            message = f"Salida terrible. Posición {position} (perdiste {delta} posiciones)."
            severity = "CRITICAL"
            audio_priority = 4
            ttl = 15
            event_type = "start_quality_terrible"
        else:
            message = f"Salida mala. Posición {position} (perdiste {delta} posiciones)."
            severity = "WARNING"
            audio_priority = 3
            ttl = 12
            event_type = "start_quality_bad"

        if message and self.can_fire(event_type, self._cooldowns.get(event_type, 0.0)):
            self._cooldowns[event_type] = 60.0
            self._start_quality_fired = True
            alerts.append(
                self._create_alert(
                    message=message,
                    severity=severity,
                    audio_priority=audio_priority,
                    ttl=ttl,
                    dismissable=True,
                    category="position",
                    payload={"position": position, "delta": delta},
                )
            )

    def _evaluate_position_reminder(self, state: Dict[str, Any], lap_number: int, alerts: List[AlertMessage]) -> None:
        if self._position_reminder_fired:
            return
        if self._position_reminder_scheduled_lap is None:
            return
        if lap_number != self._position_reminder_scheduled_lap:
            return

        position = int(state.get("class_position", 0) or 0)
        if position <= 0:
            return

        self._position_reminder_fired = True
        if self.can_fire("position_reminder", self._cooldowns.get("position_reminder", 0.0)):
            self._cooldowns["position_reminder"] = 0.0
            alerts.append(
                self._create_alert(
                    message=f"Recordatorio: estás en la posición {position}.",
                    severity="INFO",
                    audio_priority=1,
                    ttl=5,
                    dismissable=True,
                    category="position",
                    payload={"position": position},
                )
            )

    def _evaluate_overtakes(self, state: Dict[str, Any], alerts: List[AlertMessage]) -> None:
        now = time.time()
        if now - self._last_pass_check < self.pass_check_interval:
            return
        self._last_pass_check = now

        position = int(state.get("class_position", 0) or 0)
        if position <= 0:
            return

        # Muestrear gaps (simulados con datos del state si están disponibles)
        gap_ahead = float(state.get("gap_ahead", 99.0) or 99.0)
        gap_behind = float(state.get("gap_behind", 99.0) or 99.0)

        self._gap_samples_ahead.append(gap_ahead)
        self._gap_samples_behind.append(gap_behind)

        # Mantener ventana razonable
        max_samples = int(self.max_time_to_wait / self.pass_check_interval) + 1
        if len(self._gap_samples_ahead) > max_samples:
            self._gap_samples_ahead = self._gap_samples_ahead[-max_samples:]
        if len(self._gap_samples_behind) > max_samples:
            self._gap_samples_behind = self._gap_samples_behind[-max_samples:]

        # Detectar adelantamiento por delante
        if len(self._gap_samples_ahead) >= 2:
            avg_gap = sum(self._gap_samples_ahead) / len(self._gap_samples_ahead)
            if avg_gap < 0.3 and now - self._last_pass_alert_time >= self.min_time_between_overtake_messages:
                self._last_pass_alert_time = now
                self._gap_samples_ahead = []
                alerts.append(
                    self._create_alert(
                        message="Adelantando a un rival.",
                        severity="HIGH",
                        audio_priority=2,
                        ttl=10,
                        dismissable=True,
                        category="overtake",
                        payload={"gap_ahead": avg_gap},
                    )
                )

        # Detectar ser adelantado por detrás
        if len(self._gap_samples_behind) >= 2:
            avg_gap = sum(self._gap_samples_behind) / len(self._gap_samples_behind)
            if avg_gap < 0.3 and now - self._last_pass_alert_time >= self.min_time_between_overtake_messages:
                self._last_pass_alert_time = now
                self._gap_samples_behind = []
                alerts.append(
                    self._create_alert(
                        message="Te están adelantando.",
                        severity="WARNING",
                        audio_priority=2,
                        ttl=10,
                        dismissable=True,
                        category="overtake",
                        payload={"gap_behind": avg_gap},
                    )
                )

    def _create_position_alert(self, position: int) -> AlertMessage:
        return self._create_alert(
            message=f"Posición actual: {position}",
            severity="INFO",
            audio_priority=1,
            ttl=6,
            dismissable=True,
            category="position",
            payload={"position": position},
        )

    def _create_expected_finish_alert(self, start_position: int) -> AlertMessage:
        estimated = start_position
        return self._create_alert(
            message=f"Posición esperada al finalizar: {estimated}",
            severity="INFO",
            audio_priority=1,
            ttl=10,
            dismissable=True,
            category="position",
            payload={"expected_finish": estimated},
        )

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
                "severity": severity,
                "ttl": ttl,
                "dismissable": dismissable,
                **payload,
            },
        )
