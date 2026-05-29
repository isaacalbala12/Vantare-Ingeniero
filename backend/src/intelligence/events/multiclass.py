import time
import uuid
from typing import Any, Dict, List

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage


class MulticlassEvent(RaceEvent):
    """Deterministic multiclass proximity alerts.

    Implements Crew Chief MulticlassWarnings triggers.
    """

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback)
        self.cooldowns = {
            "faster_behind": 50.0,
            "multiple_faster_behind": 45.0,
            "slower_ahead": 60.0,
            "multiple_slower_ahead": 55.0,
            "catching_slower_first": 999_999.0,
        }
        self._settlement_started: Dict[str, float] = {}
        self._settlement_delay: float = 6.0
        self._check_delay: float = 4.0

    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        num_faster: int = int(state.get("num_faster_cars", 0))
        num_slower: int = int(state.get("num_slower_cars", 0))
        includes_faster_leader: bool = bool(state.get("includes_faster_leader", False))
        first_time_catching: bool = bool(state.get("first_time_catching_slower", False))
        competitors_ahead: List[Dict[str, Any]] = state.get("competitors_ahead", []) or []
        competitors_behind: List[Dict[str, Any]] = state.get("competitors_behind", []) or []

        now = time.time()

        # Faster behind
        if num_faster > 0 and includes_faster_leader:
            key = "faster_behind"
            if key not in self._settlement_started:
                self._settlement_started[key] = now
            if now - self._settlement_started[key] >= self._settlement_delay:
                if num_faster > 1:
                    self._fire_multiclass_alert(
                        alerts, "multiple_faster_behind",
                        f"Coches más rápidos detrás luchando: {num_faster} rivales.",
                        "HIGH",
                    )
                else:
                    self._fire_multiclass_alert(
                        alerts, "faster_behind",
                        "Coche más rápido detrás.",
                        "HIGH",
                    )
                self._settlement_started.pop(key, None)
        else:
            self._settlement_started.pop("faster_behind", None)
            self._settlement_started.pop("multiple_faster_behind", None)

        # Slower ahead
        if num_slower > 0:
            key = "slower_ahead"
            if key not in self._settlement_started:
                self._settlement_started[key] = now
            if now - self._settlement_started[key] >= self._settlement_delay:
                if num_slower > 1:
                    self._fire_multiclass_alert(
                        alerts, "multiple_slower_ahead",
                        f"Coches más lentos delante: {num_slower} rivales.",
                        "MEDIUM",
                    )
                else:
                    self._fire_multiclass_alert(
                        alerts, "slower_ahead",
                        "Coche más lento delante.",
                        "MEDIUM",
                    )
                self._settlement_started.pop(key, None)
        else:
            self._settlement_started.pop("slower_ahead", None)
            self._settlement_started.pop("multiple_slower_ahead", None)

        # Catching slower (first time)
        if first_time_catching and num_slower > 0:
            alert = AlertMessage(
                event="catching_slower_first",
                alert_id=str(uuid.uuid4()),
                category="multiclass",
                message="Primera vez alcanzando coche más lento.",
                audio_priority="MEDIUM",
                severity="INFO",
                ttl=15,
                dismissable=True,
                payload={"num_slower": num_slower},
            )
            self.fire("catching_slower_first", alert, self.cooldowns["catching_slower_first"])
            alerts.append(alert)

        self.reset_tick()
        return alerts

    def _fire_multiclass_alert(self, alerts, event_type, message, audio_priority):
        alert = AlertMessage(
            event=event_type,
            alert_id=str(uuid.uuid4()),
            category="multiclass",
            message=message,
            audio_priority=audio_priority,
            severity="WARNING",
            ttl=15,
            dismissable=True,
            payload={},
        )
        self.fire(event_type, alert, self.cooldowns[event_type])
        alerts.append(alert)
