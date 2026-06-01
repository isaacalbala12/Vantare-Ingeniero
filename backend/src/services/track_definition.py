from enum import Enum
from dataclasses import dataclass, field
from typing import List


class TrackLengthClass(Enum):
    VERY_SHORT = "VERY_SHORT"
    SHORT = "SHORT"
    MEDIUM = "MEDIUM"
    LONG = "LONG"
    VERY_LONG = "VERY_LONG"


OUTLIER_PACE_LIMITS = {
    TrackLengthClass.VERY_LONG: 15,
    TrackLengthClass.LONG: 8,
    TrackLengthClass.MEDIUM: 3,
    TrackLengthClass.SHORT: 2,
    TrackLengthClass.VERY_SHORT: 2,
}

FUEL_WINDOW_LENGTH = {
    TrackLengthClass.VERY_LONG: 1,
    TrackLengthClass.LONG: 2,
    TrackLengthClass.MEDIUM: 3,
    TrackLengthClass.SHORT: 4,
    TrackLengthClass.VERY_SHORT: 5,
}

LAPS_BEFORE_GAPS = {
    TrackLengthClass.VERY_LONG: 0,
    TrackLengthClass.LONG: 1,
    TrackLengthClass.MEDIUM: 2,
    TrackLengthClass.SHORT: 3,
    TrackLengthClass.VERY_SHORT: 4,
}


def get_length_class(length: float) -> TrackLengthClass:
    if length > 20000:
        return TrackLengthClass.VERY_LONG
    if length > 10000:
        return TrackLengthClass.LONG
    if length < 1000:
        return TrackLengthClass.VERY_SHORT
    if length < 2400:
        return TrackLengthClass.SHORT
    return TrackLengthClass.MEDIUM


@dataclass
class TrackDefinition:
    name: str
    track_length: float
    sectors: int = 3
    is_oval: bool = False
    gap_points: List[float] = field(default_factory=list)
    landmarks: List[dict] = field(default_factory=list)

    def __post_init__(self):
        self.track_length_class = get_length_class(self.track_length)
        if not self.gap_points and self.track_length > 3000:
            self.gap_points = self._gen_gap_points()

    def _gen_gap_points(self) -> List[float]:
        pts = []
        t = 0.0
        while t < self.track_length - 1500:
            t += 1500
            pts.append(round(t, 3))
        if self.track_length > 50:
            pts.append(self.track_length - 50)
        return pts
