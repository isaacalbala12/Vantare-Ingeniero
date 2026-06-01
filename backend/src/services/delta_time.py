from typing import Tuple


class DeltaTime:
    """Cálculo de gaps con soporte para diferencia de vueltas (multiclase)."""

    def __init__(self, time: float, lap: int):
        self.time = time
        self.lap = lap

    def get_signed_lap_diff(self, other: "DeltaTime") -> int:
        return self.lap - other.lap

    def get_absolute_time_delta(
        self, other: "DeltaTime", best_lap: float = 0.0
    ) -> Tuple[int, float]:
        ld = self.get_signed_lap_diff(other)
        td = abs(self.time - other.time)
        if ld != 0 and best_lap > 0:
            td += abs(ld) * best_lap
        return (ld, td)
