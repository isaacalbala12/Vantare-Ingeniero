from __future__ import annotations

import logging
import random
import time
import uuid
from typing import Any, Dict, List, Optional

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage

logger = logging.getLogger("vantare.lap_counter")


class LapCounterEvent(RaceEvent):
    """Deterministic lap counter, countdown and session boundary alerts.

    Triggered primarily by an explicit ``lap_event`` flag supplied by the
    strategy service / telemetry pipeline so the event does not fire on every
    evaluation tick automatically.
    """

    MAX_PRE_LIGHTS: int = 10
    PRE_LIGHTS_POOL: List[str] = [
        "Pista fría, calienta neumáticos.",
        "Ventana de parada abierta pronto.",
        "Posición actual: {position}.",
        "Consumo de combustible dentro de lo esperado.",
        "Sin daños de consideración.",
        "Mantén concentración en la salida.",
        "Tiempo de vuelta de referencia: {best_lap}.",
        "Ritmo estable en las últimas vueltas.",
        "Estrategia a una parada.",
        "Batería cargada para el stint.",
    ]

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback=broadcast_callback)
        self._pre_lights_sent: int = 0
        self._gridwalk_90: bool = False
        self._gridwalk_60: bool = False
        self._gridwalk_30: bool = False
        self._green_sent: bool = False
        self._get_ready_sent: bool = False
        self._leader_has_won_sent: bool = False
        self._last_lap_variant: Optional[str] = None
        self._two_laps_variant: Optional[str] = None

        self.cooldowns = {
            "green_flag": 0.0,
            "get_ready": 0.0,
            "leader_has_won": 0.0,
            "last_lap": 0.0,
            "last_lap_leading": 0.0,
            "last_lap_top_three": 0.0,
            "two_to_go": 0.0,
            "two_to_go_leading": 0.0,
            "two_to_go_top_three": 0.0,
            "gridwalk_90": 0.0,
            "gridwalk_60": 0.0,
            "gridwalk_30": 0.0,
            "pre_lights": 0.0,
        }

    # ------------------------------------------------------------------ #
    # Public helpers
    # ------------------------------------------------------------------ #
    def reset_session(self) -> None:
        self._last_fired.clear()
        self._fired_in_tick.clear()
        self._pre_lights_sent = 0
        self._gridwalk_90 = False
        self._gridwalk_60 = False
        self._gridwalk_30 = False
        self._green_sent = False
        self._get_ready_sent = False
        self._leader_has_won_sent = False
        self._last_lap_variant = None
        self._two_laps_variant = None

    # ------------------------------------------------------------------ #
    # evaluate
    # ------------------------------------------------------------------ #
    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        self.reset_tick()

        lap_event: Optional[str] = state.get("lap_event")
        if not lap_event:
            return alerts

        session_type: str = str(state.get("session_type", "race")).lower()
        position: int = int(state.get("class_position", 0) or 0)
        best_lap: float = float(state.get("best_lap", 0.0) or 0.0)
        leader_has_finished: bool = bool(state.get("leader_has_finished", False))
        session_laps_left: float = float(state.get("session_laps_left", 0.0) or 0.0)
        gridwalk_seconds: Optional[int] = state.get("gridwalk_seconds")
        phase: str = str(state.get("phase", "")).upper()

        # Lights out / green flag (solo en carrera / sesión con bandera verde)
        if lap_event == "green_flag" and phase == "GREEN" and not self._green_sent:
            self._green_sent = True
            alerts.append(self._create_alert(
                event_type="green_flag",
                message="¡Bandera verde! Lights out.",
                min_interval=self.cooldowns["green_flag"],
                severity="CRITICAL",
                audio_priority="CRITICAL",
                payload={"phase": phase},
            ))

        # Gridwalk countdown
        if lap_event == "gridwalk_countdown" and isinstance(gridwalk_seconds, int):
            if gridwalk_seconds == 90 and not self._gridwalk_90:
                self._gridwalk_90 = True
                alerts.append(self._create_alert(
                    event_type="gridwalk_90",
                    message="La carrera empieza en 90 segundos.",
                    min_interval=self.cooldowns["gridwalk_90"],
                    severity="INFO",
                    audio_priority="MEDIUM",
                    payload={"gridwalk_seconds": gridwalk_seconds},
                ))
            if gridwalk_seconds == 60 and not self._gridwalk_60:
                self._gridwalk_60 = True
                alerts.append(self._create_alert(
                    event_type="gridwalk_60",
                    message="La carrera empieza en 60 segundos.",
                    min_interval=self.cooldowns["gridwalk_60"],
                    severity="INFO",
                    audio_priority="MEDIUM",
                    payload={"gridwalk_seconds": gridwalk_seconds},
                ))
            if gridwalk_seconds == 30 and not self._gridwalk_30:
                self._gridwalk_30 = True
                alerts.append(self._create_alert(
                    event_type="gridwalk_30",
                    message="La carrera empieza en 30 segundos.",
                    min_interval=self.cooldowns["gridwalk_30"],
                    severity="INFO",
                    audio_priority="MEDIUM",
                    payload={"gridwalk_seconds": gridwalk_seconds},
                ))

        # Get ready (solo una vez por evento de pre-lights)
        if lap_event in {"get_ready", "gridwalk_countdown"} and not self._get_ready_sent:
            self._get_ready_sent = True
            alerts.append(self._create_alert(
                event_type="get_ready",
                message="Prepárate.",
                min_interval=self.cooldowns["get_ready"],
                severity="HIGH",
                audio_priority="HIGH",
                payload={"phase": phase},
            ))

        # Pre-lights messages aleatorios
        if lap_event == "pre_lights" and self._pre_lights_sent < self.MAX_PRE_LIGHTS:
            if self.can_fire("pre_lights", self.cooldowns.get("pre_lights", 0.0)):
                self._pre_lights_sent += 1
                text = random.choice(self.PRE_LIGHTS_POOL)
                text = text.replace("{position}", str(position))
                text = text.replace("{best_lap}", f"{best_lap:.2f}" if best_lap > 0 else "sin tiempo")
                alerts.append(self._create_alert(
                    event_type="pre_lights",
                    message=text,
                    min_interval=self.cooldowns["pre_lights"],
                    severity="INFO",
                    audio_priority="LOW",
                    payload={
                        "pre_lights_count": self._pre_lights_sent,
                        "max_pre_lights": self.MAX_PRE_LIGHTS,
                    },
                ))

        # Leader has won
        if lap_event == "leader_has_won" and leader_has_finished and not self._leader_has_won_sent:
            self._leader_has_won_sent = True
            alerts.append(self._create_alert(
                event_type="leader_has_won",
                message="El líder ha ganado la carrera.",
                min_interval=self.cooldowns["leader_has_won"],
                severity="HIGH",
                audio_priority="HIGH",
                payload={"leader_has_finished": True},
            ))

        # Last lap y 2 laps to go (solo en modo carrera)
        if session_type == "race":
            if lap_event == "last_lap" and self._last_lap_variant is None:
                variant = self._pick_last_lap_variant(position)
                self._last_lap_variant = variant
                alerts.append(self._create_alert(
                    event_type=variant,
                    message=self._last_lap_message(variant),
                    min_interval=self.cooldowns[variant],
                    severity="HIGH",
                    audio_priority="HIGH",
                    payload={"position": position, "session_laps_left": session_laps_left},
                ))

            if lap_event == "two_laps_to_go" and self._two_laps_variant is None:
                variant = self._pick_two_laps_variant(position)
                self._two_laps_variant = variant
                alerts.append(self._create_alert(
                    event_type=variant,
                    message=self._two_laps_message(variant),
                    min_interval=self.cooldowns[variant],
                    severity="HIGH",
                    audio_priority="HIGH",
                    payload={"position": position, "session_laps_left": session_laps_left},
                ))

        return alerts

    # ------------------------------------------------------------------ #
    # Helpers privados
    # ------------------------------------------------------------------ #
    def _create_alert(
        self,
        event_type: str,
        message: str,
        min_interval: float = 0.0,
        severity: str = "INFO",
        audio_priority: str = "MEDIUM",
        payload: Optional[Dict[str, Any]] = None,
    ) -> AlertMessage:
        alert = AlertMessage(
            event=event_type,
            alert_id=str(uuid.uuid4()),
            category="lap_counter",
            message=message,
            audio_priority=audio_priority,
            severity=severity,
            ttl=12,
            dismissable=True,
            payload=payload or {},
        )
        self.fire(event_type, alert, min_interval)
        return alert

    def _pick_last_lap_variant(self, position: int) -> str:
        if position == 1:
            return "last_lap_leading"
        if 1 < position < 4:
            return "last_lap_top_three"
        return "last_lap"

    def _pick_two_laps_variant(self, position: int) -> str:
        if position == 1:
            return "two_to_go_leading"
        if 1 < position < 4:
            return "two_to_go_top_three"
        return "two_to_go"

    def _last_lap_message(self, variant: str) -> str:
        return {
            "last_lap": "Última vuelta de carrera.",
            "last_lap_leading": "Última vuelta y lideras.",
            "last_lap_top_three": "Última vuelta. Posición en el podio.",
        }.get(variant, "Última vuelta.")

    def _two_laps_message(self, variant: str) -> str:
        return {
            "two_to_go": "Quedan dos vueltas.",
            "two_to_go_leading": "Quedan dos vueltas y lideras.",
            "two_to_go_top_three": "Quedan dos vueltas. Posición en el podio.",
        }.get(variant, "Quedan dos vueltas.")

