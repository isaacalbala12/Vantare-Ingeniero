"""DamageReporting — Detecta impactos, pinchazos, vuelcos, y danos por componente."""

import logging
from typing import Optional

from src.intelligence.base_event import AbstractEvent
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage, contents
from src.intelligence.event_flags import event_flags

logger = logging.getLogger("vantare.damage")

_ROLLOVER_ROLL = 45.0
_ROLLOVER_PITCH = 60.0
_WARN_ROLL = 25.0  # Early warning threshold
_CRITICAL_ROLL = 35.0  # Critical warning
_HEAVY_IMPACT_MAG = 5.0
_PUNCTURE_PRESSURE = 5.0
_MIN_SPEED_FOR_PUNCTURE_CHECK = 2.0
_MIN_SPEED_FOR_ROLLOVER_CHECK = 1.0
_CLEAR_WAIT_SECONDS = 10.0


class DamageReporting(AbstractEvent):
    applicable_session_types = [
        SessionType.PRACTICE, SessionType.QUALIFY, SessionType.RACE
    ]
    applicable_session_phases = [
        SessionPhase.GREEN, SessionPhase.FULL_COURSE_YELLOW
    ]
    message_category = "DAMAGE"
    sequence = 35

    def __init__(self, audio_player=None):
        super().__init__(audio_player=audio_player)
        self._last_impact_time: float = -1.0
        self._damage_reported: set = set()
        self._puncture_reported: list = []
        self._rollover_reported: bool = False
        self._impact_reported_time: float = 0.0

    def trigger_internal(
        self, previous: Optional[GameStateData], current: GameStateData
    ) -> None:
        if current is None:
            return

        damage = current.damage
        now = current.now

        # Impact detection
        impact_time = damage.last_impact_time
        impact_mag = damage.last_impact_magnitude
        if (impact_time > 0 and impact_mag > 0 and
                impact_time != self._last_impact_time):
            self._last_impact_time = impact_time
            if impact_mag >= _HEAVY_IMPACT_MAG:
                event_flags.waiting_for_driver_is_ok_response = True
                self.play_message_immediately(QueuedMessage(
                    "damage/impact", expires=15, priority=15,
                    fragments=contents("heavy impact, check your car"),
                ))
                self._impact_reported_time = now
            else:
                self.play_message(QueuedMessage(
                    "damage/damage_reporting", expires=10, priority=8,
                    fragments=contents("impact detected"),
                ))

        # Check waiting_for_driver_is_ok timeout
        if event_flags.waiting_for_driver_is_ok_response:
            if now - self._impact_reported_time > _CLEAR_WAIT_SECONDS:
                event_flags.waiting_for_driver_is_ok_response = False

        # Aero damage
        aero = getattr(damage, "aero", "NONE")
        if aero != "NONE" and "aero" not in self._damage_reported:
            self.play_message(QueuedMessage(
                "damage/aero_damage", expires=10, priority=10,
                fragments=contents("aero damage, expect less downforce"),
            ))
            self._damage_reported.add("aero")

        # Suspension damage per corner
        susp = getattr(damage, "suspension", ["NONE"] * 4)
        corners = ["fl", "fr", "rl", "rr"]
        for i, key in enumerate(corners):
            if i < len(susp) and susp[i] != "NONE":
                dkey = f"suspension_{key}"
                if dkey not in self._damage_reported:
                    self.play_message(QueuedMessage(
                        f"damage/{dkey}", expires=10, priority=10,
                        fragments=contents(f"suspension damage {key}"),
                    ))
                    self._damage_reported.add(dkey)

        # Puncture detection (0 pressure + stopped)
        tyre = current.tyre
        pressures = [tyre.fl_pressure, tyre.fr_pressure, tyre.rl_pressure, tyre.rr_pressure]
        speed = current.motion.car_speed

        if speed <= _MIN_SPEED_FOR_PUNCTURE_CHECK:
            for i, key in enumerate(corners):
                if 0 < pressures[i] <= _PUNCTURE_PRESSURE and key not in self._puncture_reported:
                    self.play_message_immediately(QueuedMessage(
                        f"damage/puncture_{key}", expires=10, priority=15,
                        fragments=contents(f"puncture on {key}"),
                    ))
                    self._puncture_reported.append(key)

        # Progressive rollover detection
        roll = current.motion.orientation.roll
        pitch = current.motion.orientation.pitch
        if speed <= _MIN_SPEED_FOR_ROLLOVER_CHECK:
            # Early warning at 25° roll or 35° pitch
            if abs(roll) > _WARN_ROLL or abs(pitch) > _CRITICAL_ROLL:
                if not self._rollover_reported:
                    severity = "car leaning"
                    if abs(roll) > _ROLLOVER_ROLL or abs(pitch) > _ROLLOVER_PITCH:
                        severity = "rollover detected"
                        event_flags.waiting_for_driver_is_ok_response = True
                    self.play_message_immediately(QueuedMessage(
                        "damage/rollover" if severity == "rollover detected" else "damage/rollover_warning",
                        expires=30 if severity == "rollover detected" else 10,
                        priority=15,
                        fragments=contents(severity),
                    ))
                    self._rollover_reported = True
            else:
                self._rollover_reported = False

    def clear_state(self) -> None:
        self._last_impact_time = -1.0
        self._damage_reported.clear()
        self._puncture_reported.clear()
        self._rollover_reported = False
        self._impact_reported_time = 0.0
