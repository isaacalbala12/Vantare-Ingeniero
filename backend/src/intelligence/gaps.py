from src.intelligence.state_coercion import lmu_scalar


def _sanitize_gap(value, default: float = 99.0) -> float:
    gap = float(lmu_scalar(value, default=default))
    if 0.0 <= gap <= 3600.0:
        return gap
    return default


def resolve_gaps(telemetry: dict) -> tuple[float, float]:
    """Resolve ahead/behind gaps from multiple telemetry sources."""
    ahead_candidates = (
        telemetry.get("time_gap_car_ahead"),
        telemetry.get("time_gap_place_ahead"),
        telemetry.get("gap_ahead"),
    )
    behind_candidates = (
        telemetry.get("time_gap_car_behind"),
        telemetry.get("time_gap_place_behind"),
        telemetry.get("gap_behind"),
    )

    gap_ahead = 99.0
    for candidate in ahead_candidates:
        value = _sanitize_gap(candidate, default=99.0)
        if value != 99.0:
            gap_ahead = value
            break

    gap_behind = 99.0
    for candidate in behind_candidates:
        value = _sanitize_gap(candidate, default=99.0)
        if value != 99.0:
            gap_behind = value
            break

    return gap_ahead, gap_behind
