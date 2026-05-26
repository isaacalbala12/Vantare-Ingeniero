import time
from typing import Optional

from shared_strategy.models import TelemetryFrame


class StateChangeDetector:
    """Detects state changes between consecutive TelemetryFrame instances."""

    def __init__(self) -> None:
        self._prev_frame: Optional[TelemetryFrame] = None
        self._lap_snapshots: list[dict] = []

    def detect(self, frame: TelemetryFrame) -> list[dict]:
        """Detect state changes and return list of events."""
        events: list[dict] = []

        if self._prev_frame is None:
            self._prev_frame = frame
            return events

        prev = self._prev_frame

        # Position change
        if abs(frame.lap_distance - prev.lap_distance) > 5.0:
            events.append({
                "type": "position_change",
                "lap": frame.lap_number,
                "timestamp": time.time(),
                "data": {
                    "from": prev.lap_distance,
                    "to": frame.lap_distance,
                    "delta": frame.lap_distance - prev.lap_distance,
                },
            })

        # Pit entry
        if not prev.in_pits and frame.in_pits:
            events.append({
                "type": "pit_entry",
                "lap": frame.lap_number,
                "timestamp": time.time(),
                "data": {"lap_number": frame.lap_number},
            })

        # Pit exit
        if prev.in_pits and not frame.in_pits:
            events.append({
                "type": "pit_exit",
                "lap": frame.lap_number,
                "timestamp": time.time(),
                "data": {"lap_number": frame.lap_number},
            })

        # Gap change
        if frame.lap_number != prev.lap_number:
            events.append({
                "type": "gap_change",
                "lap": frame.lap_number,
                "timestamp": time.time(),
                "data": {
                    "from_lap": prev.lap_number,
                    "to_lap": frame.lap_number,
                },
            })

        # Safety car
        if frame.safety_car_active != prev.safety_car_active:
            events.append({
                "type": "safety_car",
                "lap": frame.lap_number,
                "timestamp": time.time(),
                "data": {"active": frame.safety_car_active},
            })

        # Lap completed
        if frame.lap_number > prev.lap_number:
            events.append({
                "type": "lap_completed",
                "lap": frame.lap_number,
                "timestamp": time.time(),
                "data": {
                    "lap_number": frame.lap_number,
                    "fuel_used": frame.fuel_used_lap_raw,
                    "avg_speed": frame.speed,
                },
            })

            # Per-lap snapshot (FIFO, max 200)
            snapshot = {
                "lap": frame.lap_number,
                "fuel_used_lap": frame.fuel_used_lap_raw,
                "avg_speed": frame.speed,
                "tyre_wear": [
                    frame.tyre_wear_fl,
                    frame.tyre_wear_fr,
                    frame.tyre_wear_rl,
                    frame.tyre_wear_rr,
                ],
                "brake_wear": [
                    frame.brake_wear_fl,
                    frame.brake_wear_fr,
                    frame.brake_wear_rl,
                    frame.brake_wear_rr,
                ],
                "timestamp": time.time(),
            }
            self._lap_snapshots.append(snapshot)
            if len(self._lap_snapshots) > 200:
                self._lap_snapshots.pop(0)

        # Yellow flag
        if frame.yellow_flag_active != prev.yellow_flag_active:
            events.append({
                "type": "yellow_flag",
                "lap": frame.lap_number,
                "timestamp": time.time(),
                "data": {"active": frame.yellow_flag_active},
            })

        # Weather change (always empty - no weather API access)
        # Reserved for future implementation

        self._prev_frame = frame
        return events
