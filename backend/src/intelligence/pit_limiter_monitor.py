"""Monitor de pit limiter estilo Crew Chief para SpotterService."""

from __future__ import annotations

import math
import time
from typing import Callable, List, Optional

from src.models.messages import AlertMessage


class PitLimiterMonitor:
    PIT_EXIT_DEBOUNCE_S = 2.0

    def __init__(
        self,
        *,
        grace_s: float,
        exit_check_s: float,
        min_speed_ms: float,
        entry_window_s: float,
        disengage_window_s: float,
        cooldown_s: float,
        create_alert: Callable[..., AlertMessage],
    ) -> None:
        self.grace_s = grace_s
        self.exit_check_s = exit_check_s
        self.min_speed_ms = min_speed_ms
        self.entry_window_s = entry_window_s
        self.disengage_window_s = disengage_window_s
        self.cooldown_s = cooldown_s
        self._create_alert = create_alert
        self._prev_in_pits = False
        self._pit_enter_at: Optional[float] = None
        self._pit_exit_at: Optional[float] = None
        self._limiter_exit_check_at: Optional[float] = None
        self._limiter_confirmed_on_stop = False
        self._warned_engage = False
        self._warned_disengage = False
        self._limiter_disengage_pending = False
        self._last_limiter_disengage_at = 0.0
        self._had_limiter_on_stop = False
        self._pit_left_at: Optional[float] = None

    @staticmethod
    def _speed_ms(tick: dict) -> float:
        return math.hypot(float(tick.get("vel_x", 0)), float(tick.get("vel_z", 0)))

    def evaluate(self, tick: dict) -> List[AlertMessage]:
        now = time.monotonic()
        in_pits = bool(tick.get("in_pits", False))
        limiter = bool(tick.get("pit_limiter_active", False))
        speed = self._speed_ms(tick)
        alerts: List[AlertMessage] = []

        if in_pits and not self._prev_in_pits:
            if self._pit_left_at is None or (now - self._pit_left_at) >= self.PIT_EXIT_DEBOUNCE_S:
                self._pit_enter_at = now
                self._warned_engage = False
                self._limiter_confirmed_on_stop = False
                self._had_limiter_on_stop = False
            self._limiter_disengage_pending = False
            self._pit_left_at = None

        if not in_pits and self._prev_in_pits:
            self._pit_left_at = now
            self._pit_exit_at = now
            self._limiter_exit_check_at = now + self.exit_check_s
            if self._had_limiter_on_stop or limiter:
                self._limiter_disengage_pending = True
            self._warned_disengage = False

        if in_pits:
            if limiter:
                self._limiter_confirmed_on_stop = True
                self._had_limiter_on_stop = True
            self._pit_exit_at = None
            self._limiter_disengage_pending = False

        if in_pits and not limiter and not self._warned_engage:
            within_entry = (
                self._pit_enter_at is not None
                and (now - self._pit_enter_at) <= self.entry_window_s
            )
            if (
                within_entry
                and speed >= self.min_speed_ms
                and not self._limiter_confirmed_on_stop
            ):
                self._warned_engage = True
                alerts.append(
                    self._create_alert(
                        message="Pit limiter no activado al entrar en boxes.",
                        severity="CRITICAL",
                        audio_priority=4,
                        ttl=5,
                        dismissable=True,
                        category="limiter",
                        payload={
                            "limiter_event": "engage",
                            "in_pits": True,
                            "pit_limiter_active": False,
                        },
                    )
                )

        if not in_pits and not self._warned_disengage and self._had_limiter_on_stop:
            ready = (
                self._pit_exit_at is not None
                and now >= self._pit_exit_at + self.exit_check_s
            )
            if ready and limiter:
                self._warned_disengage = True
                self._limiter_disengage_pending = False
                self._last_limiter_disengage_at = now
                alerts.append(
                    self._create_alert(
                        message="Pit limiter no desactivado al salir de boxes.",
                        severity="WARNING",
                        audio_priority=3,
                        ttl=5,
                        dismissable=True,
                        category="limiter",
                        payload={
                            "limiter_event": "disengage",
                            "in_pits": False,
                            "pit_limiter_active": True,
                        },
                    )
                )

        if not in_pits and not limiter:
            if (
                self._pit_exit_at is not None
                and (now - self._pit_exit_at) > self.disengage_window_s
            ):
                self._limiter_disengage_pending = False
                self._had_limiter_on_stop = False

        self._prev_in_pits = in_pits
        return alerts
