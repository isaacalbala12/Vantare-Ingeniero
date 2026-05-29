import time
import uuid
import random
from typing import Any, Dict, List

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage


class FlagsEvent(RaceEvent):
    """Deterministic flag and safety car alerts.

    Implements Crew Chief FlagsMonitor triggers.
    """

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback)
        self.cooldowns = {
            "yellow_sector": 13.0,
            "double_yellow_sector": 10.0,
            "green_sector": 3.0,
            "fcy_start": 15.0,
            "fcy_pits_closed": 15.0,
            "fcy_pits_open": 15.0,
            "fcy_last_lap_next": 15.0,
            "fcy_prepare_green": 15.0,
            "fcy_green": 15.0,
            "local_yellow_ahead": 25.0,
            "local_yellow_clear": 25.0,
            "blue_flag": 15.0,
            "white_flag": 15.0,
            "black_flag": 15.0,
        }
        self._prev_sector_flags: Dict[int, str] = {}
        self._prev_fcy_phase: str = ""
        self._prev_local_yellow: bool = False
        self._played_white: bool = False
        self._played_black: bool = False

    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        sector_flags: Dict[int, str] = state.get("sector_flags", {}) or {}
        fcy_phase: str = str(state.get("fcy_phase", ""))
        is_local_yellow: bool = bool(state.get("is_local_yellow", False))
        local_yellow_distance: float = float(state.get("local_yellow_distance", 9999.0))
        opponent_position: int = int(state.get("opponent_position", 0))
        player_position: int = int(state.get("player_position", 0))
        current_flag: str = str(state.get("current_flag", ""))

        # Sector flags transitions
        for sector in (1, 2, 3):
            flag = sector_flags.get(sector, "GREEN")
            prev = self._prev_sector_flags.get(sector, "GREEN")
            if flag != prev:
                if flag == "YELLOW" and prev == "GREEN":
                    self._fire_sector_flag(alerts, sector, "yellow_flag", "Bandera amarilla en sector", "yellow_sector")
                elif flag == "DOUBLE_YELLOW" and prev in ("GREEN", "YELLOW"):
                    self._fire_sector_flag(alerts, sector, "double_yellow", "Doble amarilla en sector", "double_yellow_sector")
                elif flag == "GREEN" and prev in ("YELLOW", "DOUBLE_YELLOW"):
                    self._fire_sector_flag(alerts, sector, "green_flag", "Bandera verde en sector", "green_sector")
            self._prev_sector_flags[sector] = flag

        # FCY phases
        if fcy_phase and fcy_phase != self._prev_fcy_phase:
            phase_map = {
                "START": ("fcy_start", "Full Course Yellow: inicio"),
                "PITS_CLOSED": ("fcy_pits_closed", "Full Course Yellow: boxes cerrados"),
                "PITS_OPEN": ("fcy_pits_open", "Full Course Yellow: boxes abiertos"),
                "LAST_LAP_NEXT": ("fcy_last_lap_next", "Full Course Yellow: última vuelta bajo FCY"),
                "PREPARE_FOR_GREEN": ("fcy_prepare_green", "Full Course Yellow: prepárate para bandera verde"),
                "GREEN": ("fcy_green", "Full Course Yellow finalizado: bandera verde"),
            }
            if fcy_phase in phase_map:
                event_type, message = phase_map[fcy_phase]
                alert = AlertMessage(
                    event=event_type,
                    alert_id=str(uuid.uuid4()),
                    category="flags",
                    message=message,
                    audio_priority="HIGH",
                    severity="WARNING",
                    ttl=15,
                    dismissable=True,
                    payload={"fcy_phase": fcy_phase},
                )
                self.fire(event_type, alert, self.cooldowns[event_type])
                alerts.append(alert)
        self._prev_fcy_phase = fcy_phase

        # Local yellow
        if is_local_yellow and local_yellow_distance < 300.0:
            alert = AlertMessage(
                event="local_yellow_ahead",
                alert_id=str(uuid.uuid4()),
                category="flags",
                message="Bandera local amarilla ahead.",
                audio_priority="MEDIUM",
                severity="WARNING",
                ttl=10,
                dismissable=True,
                payload={"distance_m": local_yellow_distance},
            )
            self.fire("local_yellow_ahead", alert, self.cooldowns["local_yellow_ahead"])
            alerts.append(alert)
        if not is_local_yellow and self._prev_local_yellow:
            alert = AlertMessage(
                event="local_yellow_clear",
                alert_id=str(uuid.uuid4()),
                category="flags",
                message="Bandera local despejada.",
                audio_priority="LOW",
                severity="INFO",
                ttl=10,
                dismissable=True,
                payload={},
            )
            self.fire("local_yellow_clear", alert, self.cooldowns["local_yellow_clear"])
            alerts.append(alert)
        self._prev_local_yellow = is_local_yellow

        # Blue flag
        if opponent_position == player_position + 1 and player_position > 0:
            alert = AlertMessage(
                event="blue_flag",
                alert_id=str(uuid.uuid4()),
                category="flags",
                message="Bandera azul: coche más rápido detrás.",
                audio_priority="HIGH",
                severity="WARNING",
                ttl=10,
                dismissable=True,
                payload={"opponent_position": opponent_position},
            )
            self.fire("blue_flag", alert, self.cooldowns["blue_flag"])
            alerts.append(alert)

        # White / Black flags (once per session unless flag changes)
        if current_flag == "WHITE" and not self._played_white:
            alert = AlertMessage(
                event="white_flag",
                alert_id=str(uuid.uuid4()),
                category="flags",
                message="Bandera blanca: última vuelta.",
                audio_priority="HIGH",
                severity="INFO",
                ttl=10,
                dismissable=True,
                payload={},
            )
            self.fire("white_flag", alert, self.cooldowns["white_flag"])
            alerts.append(alert)
            self._played_white = True
        if current_flag == "BLACK" and not self._played_black:
            alert = AlertMessage(
                event="black_flag",
                alert_id=str(uuid.uuid4()),
                category="flags",
                message="Bandera negra: debes entrar a boxes.",
                audio_priority="CRITICAL",
                severity="CRITICAL",
                ttl=15,
                dismissable=False,
                payload={},
            )
            self.fire("black_flag", alert, self.cooldowns["black_flag"])
            alerts.append(alert)
            self._played_black = True

        self.reset_tick()
        return alerts

    def _fire_sector_flag(self, alerts, sector, event_type, message, cooldown_key):
        alert = AlertMessage(
            event=event_type,
            alert_id=str(uuid.uuid4()),
            category="flags",
            message=f"{message} {sector}",
            audio_priority="HIGH",
            severity="WARNING",
            ttl=10,
            dismissable=True,
            payload={"sector": sector},
        )
        self.fire(cooldown_key, alert, self.cooldowns[cooldown_key])
        alerts.append(alert)
