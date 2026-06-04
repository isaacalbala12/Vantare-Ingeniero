"""TyreMonitor — Temperaturas, desgaste, bloqueos, presiones por corner.

Usa thresholds de car_class_data por compuesto (Soft/Medium/Hard/Wet).
Anti-spam: cada warning tipo tiene un intervalo minimo de 30s entre emisiones.
"""

import time
import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents
from src.intelligence.event_flags import event_flags

logger = logging.getLogger("vantare.tyre_monitor")

_DEFAULT_OVERHEAT_THRESHOLD = 110.0
_DEFAULT_COLD_THRESHOLD = 70.0
_DEFAULT_PRESSURE_HIGH = 220.0
_DEFAULT_PRESSURE_LOW = 100.0
_WEAR_WARNING_THRESHOLD = 0.80
_LOCKUP_TEMP_SPIKE = 15.0
_LOCKUP_PRESS_DROP = 5.0
_MIN_SPEED_FOR_LOCKUP = 5.0
_MIN_MSG_INTERVAL = 30.0

CORNERS = [
    ("fl", "front left"),
    ("fr", "front right"),
    ("rl", "rear left"),
    ("rr", "rear right"),
]


class TyreMonitor(AbstractEvent):
    applicable_session_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_session_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW
    ]
    message_category = "TYRES"
    sequence = 30

    # Default compound thresholds (fallback if car_class_data lookup fails)
    COMPOUND_THRESHOLDS = {
        "Soft": {"cooking": 110.0, "warm": 50.0},
        "Medium": {"cooking": 115.0, "warm": 55.0},
        "Hard": {"cooking": 120.0, "warm": 60.0},
        "Wet": {"cooking": 65.0, "warm": 30.0},
    }

    def __init__(self, audio_player=None):
        super().__init__(audio_player=audio_player)
        self._prev_temps = [0.0, 0.0, 0.0, 0.0]
        self._prev_pressures = [0.0, 0.0, 0.0, 0.0]
        self._lockup_reported = [False, False, False, False]
        self._wear_announced: bool = False
        self._last_compound: str = "Unknown_Race"
        self._compound_change_announced: bool = False
        # Anti-spam timestamps per corner per message type
        self._overheat_last_time: list = [0.0, 0.0, 0.0, 0.0]
        self._cold_last_time: list = [0.0, 0.0, 0.0, 0.0]
        self._pressure_high_last_time: list = [0.0, 0.0, 0.0, 0.0]
        self._pressure_low_last_time: list = [0.0, 0.0, 0.0, 0.0]

    def _get_thresholds(self, compound: str) -> dict:
        # Try car_class_data first (compound thresholds from TYRE_TEMP_THRESHOLDS)
        try:
            from src.data.car_class_data import get_tyre_thresholds, TyreTemp
            thresholds = get_tyre_thresholds(compound)
            if thresholds:
                cooking = next(
                    (t.lower for t in thresholds if t.name == TyreTemp.COOKING),
                    _DEFAULT_OVERHEAT_THRESHOLD,
                )
                warm = next(
                    (t.lower for t in thresholds if t.name == TyreTemp.WARM),
                    _DEFAULT_COLD_THRESHOLD,
                )
                return {"cooking": float(cooking), "warm": float(warm)}
        except Exception:
            pass
        # Fallback: hardcoded compound-specific defaults
        if compound in self.COMPOUND_THRESHOLDS:
            return self.COMPOUND_THRESHOLDS[compound]
        return {"cooking": _DEFAULT_OVERHEAT_THRESHOLD, "warm": _DEFAULT_COLD_THRESHOLD}

    def _can_emit(self, last_times: list, idx: int, now: float) -> bool:
        """Check if MIN_MSG_INTERVAL has passed since last emission for this corner+type."""
        if now - last_times[idx] >= _MIN_MSG_INTERVAL:
            last_times[idx] = now
            return True
        return False

    def _temps(self, tyre) -> list:
        return [tyre.fl_temp, tyre.fr_temp, tyre.rl_temp, tyre.rr_temp]

    def _pressures(self, tyre) -> list:
        return [tyre.fl_pressure, tyre.fr_pressure, tyre.rl_pressure, tyre.rr_pressure]

    def _wears(self, tyre) -> list:
        return [tyre.fl_wear, tyre.fr_wear, tyre.rl_wear, tyre.rr_wear]

    def trigger_internal(
        self, previous: Optional[GameStateData], current: GameStateData
    ) -> None:
        if current is None:
            return

        tyre = current.tyre
        temps = self._temps(tyre)
        pressures = self._pressures(tyre)
        wears = self._wears(tyre)
        compound = tyre.fl_compound
        speed = current.motion.car_speed
        now = current.now

        # Get compound thresholds
        th = self._get_thresholds(compound)
        overheat_th = th.get("cooking", _DEFAULT_OVERHEAT_THRESHOLD)
        warm_th = th.get("warm", _DEFAULT_COLD_THRESHOLD)
        cold_th = warm_th - 10.0  # cold is 10 below warm threshold

        # Compound change detection
        if compound != self._last_compound:
            if not self._compound_change_announced and self._last_compound != "Unknown_Race":
                self.play_message(QueuedMessage(
                    "tyre_monitor/compound_change", expires=10, priority=8,
                    fragments=contents("tyre compound changed"),
                ))
                self._compound_change_announced = True
            self._last_compound = compound
        else:
            self._compound_change_announced = False

        # Check each corner
        for i, (code, name) in enumerate(CORNERS):
            # Temperature warnings (anti-spam: 30s)
            if temps[i] >= overheat_th:
                if self._can_emit(self._overheat_last_time, i, now):
                    self.play_message(QueuedMessage(
                        f"tyre_monitor/{code}_overheating", expires=10, priority=8,
                        fragments=contents(f"{name} overheating"),
                    ))
            elif temps[i] <= cold_th and temps[i] > 0:
                if self._can_emit(self._cold_last_time, i, now):
                    self.play_message(QueuedMessage(
                        f"tyre_monitor/{code}_cold", expires=10, priority=6,
                        fragments=contents(f"{name} too cold"),
                    ))

            # Pressure warnings (anti-spam: 30s)
            if pressures[i] >= _DEFAULT_PRESSURE_HIGH:
                if self._can_emit(self._pressure_high_last_time, i, now):
                    self.play_message(QueuedMessage(
                        f"tyre_monitor/{code}_pressure_high", expires=10, priority=6,
                        fragments=contents(f"{name} pressure high"),
                    ))
            elif 0 < pressures[i] <= _DEFAULT_PRESSURE_LOW:
                if self._can_emit(self._pressure_low_last_time, i, now):
                    self.play_message(QueuedMessage(
                        f"tyre_monitor/{code}_pressure_low", expires=10, priority=6,
                        fragments=contents(f"{name} pressure low"),
                    ))

            # Lockup detection (temp spike + pressure drop)
            # Only detect if we have a valid previous reading (avoid false positive on first tick)
            if speed >= _MIN_SPEED_FOR_LOCKUP:
                if self._prev_temps[i] > 0 and self._prev_pressures[i] > 0:
                    temp_rise = temps[i] - self._prev_temps[i]
                    press_drop = self._prev_pressures[i] - pressures[i]
                    if temp_rise > _LOCKUP_TEMP_SPIKE and press_drop > _LOCKUP_PRESS_DROP:
                        if not self._lockup_reported[i]:
                            self.play_message(QueuedMessage(
                                f"tyre_monitor/{code}_locking", expires=5, priority=12,
                                fragments=contents(f"{name} locking"),
                            ))
                            self._lockup_reported[i] = True
                    else:
                        self._lockup_reported[i] = False

        # Wear warning (any corner > 80%) — already has anti-spam via _wear_announced
        if not self._wear_announced:
            for i, w in enumerate(wears):
                if w >= _WEAR_WARNING_THRESHOLD:
                    self.play_message(QueuedMessage(
                        "tyre_monitor/wear_warning", expires=10, priority=10,
                        fragments=contents("tyre wear above 80 percent"),
                    ))
                    self._wear_announced = True
                    break

        self._prev_temps = temps
        self._prev_pressures = pressures

    def clear_state(self) -> None:
        self._prev_temps = [0.0, 0.0, 0.0, 0.0]
        self._prev_pressures = [0.0, 0.0, 0.0, 0.0]
        self._lockup_reported = [False, False, False, False]
        self._wear_announced = False
        self._last_compound = "Unknown_Race"
        self._compound_change_announced = False
        self._overheat_last_time = [0.0, 0.0, 0.0, 0.0]
        self._cold_last_time = [0.0, 0.0, 0.0, 0.0]
        self._pressure_high_last_time = [0.0, 0.0, 0.0, 0.0]
        self._pressure_low_last_time = [0.0, 0.0, 0.0, 0.0]
