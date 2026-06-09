from __future__ import annotations


def normalize_display_sector(raw: int) -> int:
    """LMU mSector: 0=S3, 1=S1, 2=S2 → display 1, 2, 3."""
    return {0: 3, 1: 1, 2: 2}.get(int(raw), int(raw))


def read_sector(telemetry: dict) -> int:
    raw = telemetry.get("current_sector")
    if raw is None:
        raw = telemetry.get("sector")
    if raw is None:
        raw = telemetry.get("mSector")
    return int(raw if raw is not None else 1)


def lap_completed(previous: dict, current: dict) -> bool:
    prev_lap = int(previous.get("lap_number") or previous.get("completed_laps") or 0)
    curr_lap = int(current.get("lap_number") or current.get("completed_laps") or 0)
    return curr_lap > prev_lap and curr_lap > 0
