from __future__ import annotations

from enum import Enum


class GapTrend(str, Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    HOLDING = "holding"
    CLOSE = "close"


TREND_MIN_DELTA_S = 0.3
HOLDING_MAX_SPREAD_S = 0.15


def classify_gap_trend(
    samples: list[float],
    *,
    close_threshold_s: float = 1.0,
    trend_min_delta_s: float = TREND_MIN_DELTA_S,
    holding_max_spread_s: float = HOLDING_MAX_SPREAD_S,
) -> GapTrend | None:
    if len(samples) < 3:
        return None
    last_three = samples[-3:]
    if last_three[-1] < close_threshold_s:
        return GapTrend.CLOSE
    delta = last_three[-1] - last_three[0]
    spread = max(last_three) - min(last_three)
    if spread <= holding_max_spread_s:
        return GapTrend.HOLDING
    if delta >= trend_min_delta_s:
        return GapTrend.INCREASING
    if delta <= -trend_min_delta_s:
        return GapTrend.DECREASING
    return GapTrend.HOLDING
