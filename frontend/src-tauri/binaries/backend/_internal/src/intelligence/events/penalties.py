import time
import uuid
import random
from typing import Any, Dict, List

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage


class PenaltiesEvent(RaceEvent):
    """Deterministic penalty and track limits alerts.

    Implements Crew Chief Penalties triggers.
    """

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback)
        self.cooldowns = {
            "cut_track_1": 30.0,
            "cut_track_2": 30.0,
            "cut_track_3": 30.0,
            "cut_track_4": 30.0,
            "slow_down_penalty": 30.0,
            "stop_go_penalty": 30.0,
            "drive_through_penalty": 30.0,
            "penalty_served": 30.0,
            "track_limits_warning": 30.0,
        }
        self._prev_penalty_active: bool = False
        self._played_slow_down: bool = False

    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        cut_track_warnings: int = int(state.get("cut_track_warnings", 0))
        has_slow_down: bool = bool(state.get("has_slow_down_penalty", False))
        has_stop_and_go: bool = bool(state.get("has_stop_and_go", False))
        has_drive_through: bool = bool(state.get("has_drive_through", False))
        penalty_active: bool = bool(state.get("penalty_active", False))
        possible_track_limits: bool = bool(state.get("possible_track_limits", False))
        penalty_type: str = str(state.get("penalty_type", ""))
        penalty_cause: str = str(state.get("penalty_cause", ""))

        # Cut track warnings progressive
        if 1 <= cut_track_warnings <= 4:
            event_type = f"cut_track_{cut_track_warnings}"
            message = f"Aviso de corte de pista {cut_track_warnings} de 4."
            alert = AlertMessage(
                event=event_type,
                alert_id=str(uuid.uuid4()),
                category="penalties",
                message=message,
                audio_priority="HIGH",
                severity="WARNING",
                ttl=10,
                dismissable=True,
                payload={"warnings": cut_track_warnings},
            )
            # 30s + random(0, 10)
            cooldown = 30.0 + random.uniform(0, 10)
            self.fire(event_type, alert, cooldown)
            alerts.append(alert)

        # Slow down penalty (iRacing)
        if has_slow_down and not self._played_slow_down:
            alert = AlertMessage(
                event="slow_down_penalty",
                alert_id=str(uuid.uuid4()),
                category="penalties",
                message="Penalización de slow down.",
                audio_priority="HIGH",
                severity="WARNING",
                ttl=15,
                dismissable=True,
                payload={},
            )
            self.fire("slow_down_penalty", alert, self.cooldowns["slow_down_penalty"])
            alerts.append(alert)
            self._played_slow_down = True

        # Stop&Go / Drive Through
        if has_stop_and_go:
            cause_text = {
                "SPEEDING": "Speeding in pit lane",
                "CUT_TRACK": "Cut track",
            }.get(penalty_cause, penalty_cause)
            message = f"Stop and Go penalización: {cause_text}."
            alert = AlertMessage(
                event="stop_go_penalty",
                alert_id=str(uuid.uuid4()),
                category="penalties",
                message=message,
                audio_priority="CRITICAL",
                severity="CRITICAL",
                ttl=15,
                dismissable=False,
                payload={"cause": penalty_cause},
            )
            self.fire("stop_go_penalty", alert, self.cooldowns["stop_go_penalty"])
            alerts.append(alert)

        if has_drive_through:
            cause_text = {
                "SPEEDING": "Speeding in pit lane",
                "IGNORED_BLUE_FLAG": "Ignored blue flag",
            }.get(penalty_cause, penalty_cause)
            message = f"Drive Through penalización: {cause_text}."
            alert = AlertMessage(
                event="drive_through_penalty",
                alert_id=str(uuid.uuid4()),
                category="penalties",
                message=message,
                audio_priority="CRITICAL",
                severity="CRITICAL",
                ttl=15,
                dismissable=False,
                payload={"cause": penalty_cause},
            )
            self.fire("drive_through_penalty", alert, self.cooldowns["drive_through_penalty"])
            alerts.append(alert)

        # Penalty served: transition True -> False
        if self._prev_penalty_active and not penalty_active:
            alert = AlertMessage(
                event="penalty_served",
                alert_id=str(uuid.uuid4()),
                category="penalties",
                message="Penalización cumplida.",
                audio_priority="HIGH",
                severity="INFO",
                ttl=10,
                dismissable=True,
                payload={},
            )
            self.fire("penalty_served", alert, self.cooldowns["penalty_served"])
            alerts.append(alert)
        self._prev_penalty_active = penalty_active

        # Track limits warning
        if possible_track_limits:
            alert = AlertMessage(
                event="track_limits_warning",
                alert_id=str(uuid.uuid4()),
                category="penalties",
                message="Posible límite de pista.",
                audio_priority="MEDIUM",
                severity="WARNING",
                ttl=10,
                dismissable=True,
                payload={},
            )
            self.fire("track_limits_warning", alert, self.cooldowns["track_limits_warning"])
            alerts.append(alert)

        self.reset_tick()
        return alerts
