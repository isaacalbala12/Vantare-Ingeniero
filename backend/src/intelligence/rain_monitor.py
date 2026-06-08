"""Monitor de lluvia en tiempo real vía mRaining (LMU-30)."""

from __future__ import annotations

from enum import IntEnum

from src.intelligence.immediate_alert import ImmediateAlert


class RainLevel(IntEnum):
    NONE = 0
    DRIZZLE = 1
    LIGHT = 2
    MID = 3
    HEAVY = 4
    STORM = 5


RAIN_THRESHOLDS: list[tuple[float, RainLevel]] = [
    (0.0, RainLevel.NONE),
    (0.01, RainLevel.DRIZZLE),
    (0.15, RainLevel.LIGHT),
    (0.3, RainLevel.MID),
    (0.6, RainLevel.HEAVY),
    (0.75, RainLevel.STORM),
]

RAIN_MESSAGES: dict[RainLevel, str] = {
    RainLevel.DRIZZLE: "Llovizna — vigila la pista.",
    RainLevel.LIGHT: "Lluvia ligera. Prepara intermedias.",
    RainLevel.MID: "Está lloviendo. Considera entrar a por lluvia.",
    RainLevel.HEAVY: "Lluvia intensa. Entra a por mojado.",
    RainLevel.STORM: "Diluvio. Máximo cuidado.",
}


class RainLevelMonitor:
    def __init__(self) -> None:
        self._last_level = RainLevel.NONE
        self._last_alert_at: float = 0.0

    def reset_session(self) -> None:
        self._last_level = RainLevel.NONE
        self._last_alert_at = 0.0

    @staticmethod
    def _classify(raining: float) -> RainLevel:
        level = RainLevel.NONE
        for threshold, rain_level in RAIN_THRESHOLDS:
            if raining >= threshold:
                level = rain_level
        return level

    def evaluate(self, raining: float, now: float) -> ImmediateAlert | None:
        level = self._classify(raining)
        if level == self._last_level:
            return None
        if self._last_alert_at > 0 and (now - self._last_alert_at) < 120.0:
            self._last_level = level
            return None

        prev = self._last_level
        self._last_level = level
        self._last_alert_at = now

        if level == RainLevel.NONE and prev != RainLevel.NONE:
            return ImmediateAlert(
                "rain_stopped",
                "Dejó de llover. Pista secándose.",
                "MEDIUM",
                "rain",
            )

        msg = RAIN_MESSAGES.get(level)
        if not msg:
            return None
        priority = "HIGH" if level >= RainLevel.HEAVY else "MEDIUM"
        return ImmediateAlert(
            f"rain_{level.name.lower()}",
            msg,
            priority,
            "rain",
        )
