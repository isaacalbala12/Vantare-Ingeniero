import time
import uuid
from typing import Any, Dict, List

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage


class PitStopsEvent(RaceEvent):
    """Deterministic pit stop alerts.

    Implements Crew Chief PitStops triggers.
    """

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback)
        self.cooldowns = {
            "pit_window_open_lap": 10.0,
            "pit_window_open_time": 10.0,
            "pit_window_1_min": 10.0,
            "pit_window_open": 10.0,
            "pit_window_closing_2min": 10.0,
            "pit_window_closing": 10.0,
            "box_this_lap": 10.0,
            "pit_now": 10.0,
            "countdown_5": 5.0,
            "countdown_4": 5.0,
            "countdown_3": 5.0,
            "countdown_2": 5.0,
            "countdown_1": 5.0,
            "countdown_box": 5.0,
            "engage_limiter": 3.0,
            "disengage_limiter": 3.0,
            "pit_speed_limit": 2.0,
            "pit_stall_occupied": 5.0,
        }
        self._prev_in_pit_window: bool = False
        self._prev_in_pitlane: bool = False
        self._limiter_engaged: bool = False
        self._countdown_stages_fired: List[int] = []
        self._countdown_thresholds = [500, 400, 300, 200, 100, 0]  # meters

    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        pit_window_open_lap: int = int(state.get("pit_window_open_lap", 0))
        pit_window_open_time: float = float(state.get("pit_window_open_time", 0.0))
        time_to_open: float = float(state.get("time_to_open", 9999.0))
        in_pit_window: bool = bool(state.get("in_pit_window", False))
        mandatory_stop: bool = bool(state.get("mandatory_stop_box_this_lap", False))
        in_pitlane: bool = bool(state.get("in_pitlane", False))
        distance_to_pit_entry: float = float(state.get("distance_to_pit_entry", 9999.0))
        speed: float = float(state.get("speed", 0.0))
        pit_stall_occupied: bool = bool(state.get("pit_stall_occupied", False))

        # Pit window opens lap
        if pit_window_open_lap > 0:
            alert = AlertMessage(
                event="pit_window_open_lap",
                alert_id=str(uuid.uuid4()),
                category="pit_stops",
                message=f"Ventana de paradas abierta en la vuelta {pit_window_open_lap}.",
                audio_priority="MEDIUM",
                severity="INFO",
                ttl=15,
                dismissable=True,
                payload={"lap": pit_window_open_lap},
            )
            self.fire("pit_window_open_lap", alert, self.cooldowns["pit_window_open_lap"])
            alerts.append(alert)

        # Pit window opens time
        if pit_window_open_time > 0:
            minutes = int(pit_window_open_time / 60.0)
            alert = AlertMessage(
                event="pit_window_open_time",
                alert_id=str(uuid.uuid4()),
                category="pit_stops",
                message=f"Ventana de paradas abierta en {minutes} minutos.",
                audio_priority="MEDIUM",
                severity="INFO",
                ttl=15,
                dismissable=True,
                payload={"minutes": minutes},
            )
            self.fire("pit_window_open_time", alert, self.cooldowns["pit_window_open_time"])
            alerts.append(alert)

        # 1 min to open
        if 0 < time_to_open < 60.0:
            alert = AlertMessage(
                event="pit_window_1_min",
                alert_id=str(uuid.uuid4()),
                category="pit_stops",
                message="Ventana de paradas abierta en 1 minuto.",
                audio_priority="HIGH",
                severity="WARNING",
                ttl=10,
                dismissable=True,
                payload={"seconds": int(time_to_open)},
            )
            self.fire("pit_window_1_min", alert, self.cooldowns["pit_window_1_min"])
            alerts.append(alert)

        # Pit window open / closing
        if in_pit_window and not self._prev_in_pit_window:
            alert = AlertMessage(
                event="pit_window_open",
                alert_id=str(uuid.uuid4()),
                category="pit_stops",
                message="Ventana de paradas abierta.",
                audio_priority="MEDIUM",
                severity="INFO",
                ttl=10,
                dismissable=True,
                payload={},
            )
            self.fire("pit_window_open", alert, self.cooldowns["pit_window_open"])
            alerts.append(alert)
        if not in_pit_window and self._prev_in_pit_window:
            alert = AlertMessage(
                event="pit_window_closing",
                alert_id=str(uuid.uuid4()),
                category="pit_stops",
                message="Ventana de paradas cerrando.",
                audio_priority="HIGH",
                severity="WARNING",
                ttl=10,
                dismissable=True,
                payload={},
            )
            self.fire("pit_window_closing", alert, self.cooldowns["pit_window_closing"])
            alerts.append(alert)
        self._prev_in_pit_window = in_pit_window

        # Box this lap (mandatory)
        if mandatory_stop:
            alert = AlertMessage(
                event="box_this_lap",
                alert_id=str(uuid.uuid4()),
                category="pit_stops",
                message="Para esta vuelta.",
                audio_priority="CRITICAL",
                severity="CRITICAL",
                ttl=10,
                dismissable=False,
                payload={},
            )
            self.fire("box_this_lap", alert, self.cooldowns["box_this_lap"])
            alerts.append(alert)

        # Countdown 5-4-3-2-1-BOX
        if in_pitlane:
            for idx, threshold in enumerate(self._countdown_thresholds):
                if distance_to_pit_entry <= threshold and idx not in self._countdown_stages_fired:
                    stage_names = ["5", "4", "3", "2", "1", "BOX"]
                    event_type = f"countdown_{stage_names[idx]}"
                    message = stage_names[idx]
                    if message == "BOX":
                        message = "BOX"
                        audio_priority = "CRITICAL"
                        severity = "CRITICAL"
                    else:
                        audio_priority = "HIGH"
                        severity = "WARNING"
                    alert = AlertMessage(
                        event=event_type,
                        alert_id=str(uuid.uuid4()),
                        category="pit_stops",
                        message=message,
                        audio_priority=audio_priority,
                        severity=severity,
                        ttl=5,
                        dismissable=True,
                        payload={"distance_m": distance_to_pit_entry},
                    )
                    self.fire(event_type, alert, self.cooldowns[event_type])
                    alerts.append(alert)
                    self._countdown_stages_fired.append(idx)
        else:
            self._countdown_stages_fired.clear()

        # Engage limiter
        if distance_to_pit_entry < 250.0 and not in_pitlane and not self._limiter_engaged:
            alert = AlertMessage(
                event="engage_limiter",
                alert_id=str(uuid.uuid4()),
                category="pit_stops",
                message="Activa limitador de velocidad.",
                audio_priority="HIGH",
                severity="WARNING",
                ttl=10,
                dismissable=True,
                payload={"distance_m": distance_to_pit_entry},
            )
            self.fire("engage_limiter", alert, self.cooldowns["engage_limiter"])
            alerts.append(alert)
            self._limiter_engaged = True

        # Disengage limiter
        if not in_pitlane and self._limiter_engaged:
            alert = AlertMessage(
                event="disengage_limiter",
                alert_id=str(uuid.uuid4()),
                category="pit_stops",
                message="Desactiva limitador de velocidad.",
                audio_priority="MEDIUM",
                severity="INFO",
                ttl=10,
                dismissable=True,
                payload={},
            )
            self.fire("disengage_limiter", alert, self.cooldowns["disengage_limiter"])
            alerts.append(alert)
            self._limiter_engaged = False

        # Pit speed limit warning
        if in_pitlane and speed > 0.5:
            alert = AlertMessage(
                event="pit_speed_limit",
                alert_id=str(uuid.uuid4()),
                category="pit_stops",
                message=f"Límite de velocidad en boxes: {speed * 3.6:.0f} km/h.",
                audio_priority="HIGH",
                severity="WARNING",
                ttl=5,
                dismissable=True,
                payload={"speed_ms": speed, "speed_kmh": round(speed * 3.6, 1)},
            )
            self.fire("pit_speed_limit", alert, self.cooldowns["pit_speed_limit"])
            alerts.append(alert)

        # Pit stall occupied
        if pit_stall_occupied:
            alert = AlertMessage(
                event="pit_stall_occupied",
                alert_id=str(uuid.uuid4()),
                category="pit_stops",
                message="Box ocupado.",
                audio_priority="HIGH",
                severity="WARNING",
                ttl=10,
                dismissable=True,
                payload={},
            )
            self.fire("pit_stall_occupied", alert, self.cooldowns["pit_stall_occupied"])
            alerts.append(alert)

        self.reset_tick()
        return alerts
