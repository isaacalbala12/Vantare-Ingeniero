import time
import uuid
from typing import Any, Dict, List

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage


class ConditionsEvent(RaceEvent):
    """Deterministic weather and track/air temperature alerts.

    Implements Crew Chief ConditionsMonitor triggers.
    """

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback)
        self.cooldowns = {
            "rain_drizzle_increasing": 120.0,
            "rain_light_increasing": 120.0,
            "rain_mid_increasing": 120.0,
            "rain_heavy_increasing": 120.0,
            "rain_storm": 120.0,
            "rain_stopped": 120.0,
            "temp_increasing": 120.0,
            "temp_decreasing": 120.0,
        }
        self._prev_rain_level: str = "NONE"
        self._prev_track_temp: float = 0.0
        self._prev_air_temp: float = 0.0

    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        rain_level: str = str(state.get("rain_level", "NONE")).upper()
        prev_rain_level: str = str(state.get("prev_rain_level", self._prev_rain_level)).upper()
        track_temp: float = float(state.get("track_temp", 0.0))
        prev_track_temp: float = float(state.get("prev_track_temp", self._prev_track_temp))
        air_temp: float = float(state.get("air_temp", 0.0))
        prev_air_temp: float = float(state.get("prev_air_temp", self._prev_air_temp))
        min_temp_delta: float = float(state.get("min_temp_delta", 0.5))

        # Rain level changes
        rain_levels = ("NONE", "DRIZZLE", "LIGHT", "MID", "HEAVY", "STORM")
        try:
            rain_idx = rain_levels.index(rain_level)
            prev_idx = rain_levels.index(prev_rain_level)
        except ValueError:
            rain_idx = 0
            prev_idx = 0

        if rain_level == "DRIZZLE" and rain_idx > prev_idx:
            self._fire_rain_alert(alerts, "rain_drizzle_increasing", "Llovizna aumentando.", "MEDIUM")
        elif rain_level == "LIGHT" and rain_idx > prev_idx:
            self._fire_rain_alert(alerts, "rain_light_increasing", "Lluvia ligera aumentando.", "MEDIUM")
        elif rain_level == "MID" and rain_idx > prev_idx:
            self._fire_rain_alert(alerts, "rain_mid_increasing", "Lluvia media aumentando.", "HIGH")
        elif rain_level == "HEAVY" and rain_idx > prev_idx:
            self._fire_rain_alert(alerts, "rain_heavy_increasing", "Lluvia intensa aumentando.", "HIGH")
        elif rain_level == "STORM":
            self._fire_rain_alert(alerts, "rain_storm", "Tormenta: máxima intensidad de lluvia.", "CRITICAL")
        elif rain_level == "NONE" and prev_rain_level != "NONE":
            self._fire_rain_alert(alerts, "rain_stopped", "Ha dejado de llover.", "INFO")

        self._prev_rain_level = rain_level

        # Temperature trends
        track_delta = track_temp - prev_track_temp
        air_delta = air_temp - prev_air_temp
        if abs(track_delta) >= min_temp_delta and abs(air_delta) >= min_temp_delta:
            if track_delta > 0 and air_delta > 0:
                alert = AlertMessage(
                    event="temp_increasing",
                    alert_id=str(uuid.uuid4()),
                    category="conditions",
                    message="Temperatura de pista y aire aumentando.",
                    audio_priority="LOW",
                    severity="INFO",
                    ttl=15,
                    dismissable=True,
                    payload={"track_delta": round(track_delta, 2), "air_delta": round(air_delta, 2)},
                )
                self.fire("temp_increasing", alert, self.cooldowns["temp_increasing"])
                alerts.append(alert)
            elif track_delta < 0 and air_delta < 0:
                alert = AlertMessage(
                    event="temp_decreasing",
                    alert_id=str(uuid.uuid4()),
                    category="conditions",
                    message="Temperatura de pista y aire disminuyendo.",
                    audio_priority="LOW",
                    severity="INFO",
                    ttl=15,
                    dismissable=True,
                    payload={"track_delta": round(track_delta, 2), "air_delta": round(air_delta, 2)},
                )
                self.fire("temp_decreasing", alert, self.cooldowns["temp_decreasing"])
                alerts.append(alert)

        self._prev_track_temp = track_temp
        self._prev_air_temp = air_temp

        self.reset_tick()
        return alerts

    def _fire_rain_alert(self, alerts, event_type, message, audio_priority):
        alert = AlertMessage(
            event=event_type,
            alert_id=str(uuid.uuid4()),
            category="conditions",
            message=message,
            audio_priority=audio_priority,
            severity="WARNING",
            ttl=15,
            dismissable=True,
            payload={},
        )
        self.fire(event_type, alert, self.cooldowns[event_type])
        alerts.append(alert)
