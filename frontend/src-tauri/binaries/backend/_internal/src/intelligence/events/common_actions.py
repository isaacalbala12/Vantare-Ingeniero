from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage

logger = logging.getLogger("vantare.common_actions")


class CommonActionsEvent(RaceEvent):
    """Simulated voice-command responses for the race engineer.

    These are not automatic race triggers. They are emitted when the caller
    sets ``voice_command`` in the state dict, for example in response to
    an external push-to-talk / speech-recognition pipeline.
    """

    SUPPORTED_COMMANDS = {
        "radio_check",
        "position_query",
        "fuel_status",
        "damage_report",
        "time_left",
    }

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback=broadcast_callback)
        self.cooldowns: Dict[str, float] = {
            command: 0.0 for command in self.SUPPORTED_COMMANDS
        }

    # ------------------------------------------------------------------ #
    # Public helpers
    # ------------------------------------------------------------------ #
    def reset_session(self) -> None:
        self._last_fired.clear()
        self._fired_in_tick.clear()

    # ------------------------------------------------------------------ #
    # evaluate
    # ------------------------------------------------------------------ #
    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        self.reset_tick()

        command: Optional[str] = state.get("voice_command")
        if not command:
            return alerts

        command = str(command).lower()
        if command not in self.SUPPORTED_COMMANDS:
            return alerts

        return [self._respond(command, state)]

    # ------------------------------------------------------------------ #
    # Response builder
    # ------------------------------------------------------------------ #
    def _respond(self, command: str, state: Dict[str, Any]) -> AlertMessage:
        if command == "radio_check":
            message = "Radio check, cambio."
            event_type = "radio_check"
            payload = {"command": command}
        elif command == "position_query":
            position = int(state.get("class_position", 0) or 0)
            message = f"Posición actual: {position}."
            event_type = "position_query"
            payload = {"command": command, "position": position}
        elif command == "fuel_status":
            fuel_in_tank = float(state.get("fuel_in_tank", 0.0) or 0.0)
            fuel_capacity = float(state.get("fuel_capacity", 0.0) or 0.0)
            laps_remaining = float(state.get("fuel_laps_remaining", 0.0) or 0.0)
            message = (
                f"Combustible: {fuel_in_tank:.1f} de {fuel_capacity:.1f} litros. "
                f"Vueltas restantes estimadas: {laps_remaining:.1f}."
            )
            event_type = "fuel_status"
            payload = {
                "command": command,
                "fuel_in_tank": fuel_in_tank,
                "fuel_capacity": fuel_capacity,
                "fuel_laps_remaining": laps_remaining,
            }
        elif command == "damage_report":
            engine_damage = float(state.get("engine_damage", 0.0) or 0.0)
            aero_damage = float(state.get("aero_damage", 0.0) or 0.0)
            suspension_damage = float(state.get("suspension_damage", 0.0) or 0.0)
            message = (
                "Daños: "
                f"motor {engine_damage*100:.0f}%, "
                f"aerodinámica {aero_damage*100:.0f}%, "
                f"suspensión {suspension_damage*100:.0f}%."
            )
            event_type = "damage_report"
            payload = {
                "command": command,
                "engine_damage": engine_damage,
                "aero_damage": aero_damage,
                "suspension_damage": suspension_damage,
            }
        elif command == "time_left":
            time_left = float(state.get("session_time_left", 0.0) or 0.0)
            laps_left = float(state.get("session_laps_left", 0.0) or 0.0)
            message = (
                f"Tiempo restante: {time_left/60.0:.1f} minutos. "
                f"Vueltas restantes: {int(laps_left) if laps_left > 0 else 'N/A'}."
            )
            event_type = "time_left"
            payload = {
                "command": command,
                "session_time_left": time_left,
                "session_laps_left": laps_left,
            }
        else:
            message = "Comando no reconocido."
            event_type = "unknown_command"
            payload = {"command": command}

        return self._create_alert(
            event_type=event_type,
            message=message,
            min_interval=self.cooldowns.get(event_type, 0.0),
            severity="INFO",
            audio_priority="MEDIUM",
            payload=payload,
        )

    # ------------------------------------------------------------------ #
    # Alert factory
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
            category="common_actions",
            message=message,
            audio_priority=audio_priority,
            severity=severity,
            ttl=12,
            dismissable=True,
            payload=payload or {},
        )
        self.fire(event_type, alert, min_interval)
        return alert
