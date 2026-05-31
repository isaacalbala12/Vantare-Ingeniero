from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage

logger = logging.getLogger("vantare.session_end")


class SessionEndEvent(RaceEvent):
    """Session finish classification alerts.

    One-shot per session with a global cooldown between messages to avoid
    overlapping announcements during the transition.
    """

    COOLDOWN_BETWEEN_MESSAGES: float = 10.0
    GLOBAL_COOLDOWN: float = 10.0

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback=broadcast_callback)
        self._finished: bool = False
        self._last_message_ts: float = 0.0

        self.cooldowns = {
            "winner": self.GLOBAL_COOLDOWN,
            "podium": self.GLOBAL_COOLDOWN,
            "good_finish": self.GLOBAL_COOLDOWN,
            "bad_finish": self.GLOBAL_COOLDOWN,
            "last_place": self.GLOBAL_COOLDOWN,
            "dnf": self.GLOBAL_COOLDOWN,
            "disqualified": self.GLOBAL_COOLDOWN,
            "pole_position": self.GLOBAL_COOLDOWN,
            "qual_practice_finish": self.GLOBAL_COOLDOWN,
            "session_end": self.GLOBAL_COOLDOWN,
        }

    # ------------------------------------------------------------------ #
    # Public helpers
    # ------------------------------------------------------------------ #
    def reset_session(self) -> None:
        self._last_fired.clear()
        self._fired_in_tick.clear()
        self._finished = False
        self._last_message_ts = 0.0

    # ------------------------------------------------------------------ #
    # evaluate
    # ------------------------------------------------------------------ #
    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        self.reset_tick()

        session_type: str = str(state.get("session_type", "race")).lower()
        if session_type not in {"race", "qualifying", "practice", "qualy"}:
            return alerts

        position: int = int(state.get("class_position", 0) or 0)
        session_finished: bool = bool(state.get("session_finished", False))
        dnf: bool = bool(state.get("dnf", False))
        disqualified: bool = bool(state.get("disqualified", False))
        is_last: bool = bool(state.get("is_last", False))
        met_expectations: Optional[bool] = state.get("met_expectations")
        total_entries: int = int(state.get("total_entries", 0) or 0)

        if not session_finished or self._finished:
            return alerts

        self._finished = True
        return self._fire_end_alerts(
            alerts=alerts,
            session_type=session_type,
            position=position,
            dnf=dnf,
            disqualified=disqualified,
            is_last=is_last,
            met_expectations=met_expectations,
            total_entries=total_entries,
        )

    # ------------------------------------------------------------------ #
    # Fire helpers
    # ------------------------------------------------------------------ #
    def _fire_end_alerts(
        self,
        alerts: List[AlertMessage],
        session_type: str,
        position: int,
        dnf: bool,
        disqualified: bool,
        is_last: bool,
        met_expectations: Optional[bool],
        total_entries: int,
    ) -> List[AlertMessage]:
        now = time.time()
        if now - self._last_message_ts < self.COOLDOWN_BETWEEN_MESSAGES and self._last_message_ts > 0:
            return alerts

        is_race = session_type == "race"
        is_qual = session_type in {"qualifying", "qualy"}

        if is_race:
            alerts.extend(self._evaluate_race_end(
                position=position,
                dnf=dnf,
                disqualified=disqualified,
                is_last=is_last,
                met_expectations=met_expectations,
            ))
        elif is_qual:
            alerts.extend(self._evaluate_qual_end(position=position))

        if alerts:
            self._last_message_ts = now
        return alerts

    def _evaluate_race_end(
        self,
        position: int,
        dnf: bool,
        disqualified: bool,
        is_last: bool,
        met_expectations: Optional[bool],
    ) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []

        if disqualified:
            alerts.append(self._create_alert(
                event_type="disqualified",
                message="Has sido descalificado.",
                min_interval=self.cooldowns["disqualified"],
                severity="CRITICAL",
                audio_priority="HIGH",
                payload={"position": position, "disqualified": True},
            ))
            return alerts

        if dnf:
            alerts.append(self._create_alert(
                event_type="dnf",
                message="No has terminado la carrera.",
                min_interval=self.cooldowns["dnf"],
                severity="WARNING",
                audio_priority="MEDIUM",
                payload={"position": position, "dnf": True},
            ))
            return alerts

        if position == 1:
            alerts.append(self._create_alert(
                event_type="winner",
                message="¡Victoria! Has ganado la carrera.",
                min_interval=self.cooldowns["winner"],
                severity="CRITICAL",
                audio_priority="HIGH",
                payload={"position": position},
            ))
            return alerts

        if 1 < position < 4:
            alerts.append(self._create_alert(
                event_type="podium",
                message=f"Podium. Posición {position}.",
                min_interval=self.cooldowns["podium"],
                severity="HIGH",
                audio_priority="HIGH",
                payload={"position": position},
            ))
            return alerts

        if met_expectations is True:
            alerts.append(self._create_alert(
                event_type="good_finish",
                message=f"Buen resultado. Posición {position}.",
                min_interval=self.cooldowns["good_finish"],
                severity="INFO",
                audio_priority="MEDIUM",
                payload={"position": position},
            ))
        elif met_expectations is False:
            alerts.append(self._create_alert(
                event_type="bad_finish",
                message=f"Resultado por debajo de lo esperado. Posición {position}.",
                min_interval=self.cooldowns["bad_finish"],
                severity="WARNING",
                audio_priority="MEDIUM",
                payload={"position": position},
            ))
        else:
            alerts.append(self._create_alert(
                event_type="session_end",
                message=f"Fin de la carrera. Posición {position}.",
                min_interval=self.cooldowns["session_end"],
                severity="INFO",
                audio_priority="LOW",
                payload={"position": position},
            ))

        if is_last:
            alerts.append(self._create_alert(
                event_type="last_place",
                message="Última posición.",
                min_interval=self.cooldowns["last_place"],
                severity="WARNING",
                audio_priority="MEDIUM",
                payload={"position": position},
            ))

        return alerts

    def _evaluate_qual_end(self, position: int) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        if position == 1:
            alerts.append(self._create_alert(
                event_type="pole_position",
                message="Pole position.",
                min_interval=self.cooldowns["pole_position"],
                severity="HIGH",
                audio_priority="HIGH",
                payload={"position": position},
            ))
        else:
            alerts.append(self._create_alert(
                event_type="qual_practice_finish",
                message=f"Fin de sesión. Posición {position}.",
                min_interval=self.cooldowns["qual_practice_finish"],
                severity="INFO",
                audio_priority="LOW",
                payload={"position": position},
            ))
        return alerts

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
            category="session_end",
            message=message,
            audio_priority=audio_priority,
            severity=severity,
            ttl=20,
            dismissable=True,
            payload=payload or {},
        )
        self.fire(event_type, alert, min_interval)
        return alert
