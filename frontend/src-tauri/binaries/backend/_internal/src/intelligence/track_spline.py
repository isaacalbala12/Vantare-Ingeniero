"""Datos de splines de pista — curvas y landmarks por distancia."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TrackSplinePoint(BaseModel):
    distance: float
    radius: float = 0.0
    banking: float = 0.0
    is_corner: bool = False
    name: str = ""


class TrackSpline(BaseModel):
    name: str
    length_m: float
    points: list[TrackSplinePoint] = Field(default_factory=list)


def _spa() -> TrackSpline:
    return TrackSpline(
        name="Spa-Francorchamps",
        length_m=7004.0,
        points=[
            TrackSplinePoint(distance=0, name="La Source", is_corner=True, radius=80),
            TrackSplinePoint(distance=800, name="Eau Rouge", is_corner=True, radius=120),
            TrackSplinePoint(distance=1200, name="Raidillon", is_corner=True, radius=100),
            TrackSplinePoint(distance=4500, name="Blanchimont", is_corner=True, radius=90),
            TrackSplinePoint(distance=6200, name="Bus Stop", is_corner=True, radius=60),
        ],
    )


def _monza() -> TrackSpline:
    return TrackSpline(
        name="Monza",
        length_m=5793.0,
        points=[
            TrackSplinePoint(distance=0, name="Rettifilo", is_corner=True, radius=70),
            TrackSplinePoint(distance=1200, name="Curva Grande", is_corner=True, radius=200),
            TrackSplinePoint(distance=2800, name="Lesmo 1", is_corner=True, radius=85),
            TrackSplinePoint(distance=3100, name="Lesmo 2", is_corner=True, radius=80),
            TrackSplinePoint(distance=5200, name="Parabolica", is_corner=True, radius=150),
        ],
    )


def _lemans() -> TrackSpline:
    return TrackSpline(
        name="Circuit de la Sarthe",
        length_m=13626.0,
        points=[
            TrackSplinePoint(distance=0, name="Dunlop", is_corner=True, radius=100),
            TrackSplinePoint(distance=3200, name="Tertre Rouge", is_corner=True, radius=90),
            TrackSplinePoint(distance=4500, name="Mulsanne", is_corner=False),
            TrackSplinePoint(distance=8200, name="Indianapolis", is_corner=True, radius=110),
            TrackSplinePoint(distance=8600, name="Arnage", is_corner=True, radius=75),
        ],
    )


def _silverstone() -> TrackSpline:
    return TrackSpline(
        name="Silverstone",
        length_m=5891.0,
        points=[
            TrackSplinePoint(distance=0, name="Abbey", is_corner=True, radius=90),
            TrackSplinePoint(distance=900, name="Farm", is_corner=True, radius=85),
            TrackSplinePoint(distance=1800, name="Copse", is_corner=True, radius=120),
            TrackSplinePoint(distance=3500, name="Maggotts", is_corner=True, radius=100),
            TrackSplinePoint(distance=5200, name="Club", is_corner=True, radius=70),
        ],
    )


def _portimao() -> TrackSpline:
    return TrackSpline(
        name="Portimao",
        length_m=4653.0,
        points=[
            TrackSplinePoint(distance=0, name="Turn 1", is_corner=True, radius=80),
            TrackSplinePoint(distance=800, name="Turn 5", is_corner=True, radius=90),
            TrackSplinePoint(distance=1600, name="Turn 8", is_corner=True, radius=70),
            TrackSplinePoint(distance=2800, name="Turn 12", is_corner=True, radius=85),
            TrackSplinePoint(distance=4000, name="Turn 15", is_corner=True, radius=75),
        ],
    )


_BUILTIN: dict[str, TrackSpline] = {
    "spa": _spa(),
    "spa-francorchamps": _spa(),
    "monza": _monza(),
    "lemans": _lemans(),
    "sarthe": _lemans(),
    "silverstone": _silverstone(),
    "portimao": _portimao(),
    "algarve": _portimao(),
}


class TrackSplineManager:
    def __init__(self) -> None:
        self._tracks: dict[str, TrackSpline] = dict(_BUILTIN)

    def load(self, track: TrackSpline) -> None:
        key = track.name.lower().replace(" ", "-")
        self._tracks[key] = track

    def get(self, track_name: str) -> TrackSpline | None:
        key = track_name.lower().replace(" ", "-")
        if key in self._tracks:
            return self._tracks[key]
        for alias, spline in self._tracks.items():
            if key in alias or alias in key:
                return spline
        return None

    def get_by_distance(self, track_name: str, distance_m: float) -> TrackSplinePoint | None:
        spline = self.get(track_name)
        if not spline or not spline.points:
            return None
        best: TrackSplinePoint | None = None
        best_delta = float("inf")
        for pt in spline.points:
            delta = abs(pt.distance - distance_m)
            if delta < best_delta:
                best_delta = delta
                best = pt
        return best

    def get_nearest_corner(self, track_name: str, distance_m: float, max_delta_m: float = 400.0) -> str:
        pt = self.get_by_distance(track_name, distance_m)
        if pt and pt.is_corner and abs(pt.distance - distance_m) <= max_delta_m:
            return pt.name
        return ""


_default_manager = TrackSplineManager()


def get_track_manager() -> TrackSplineManager:
    return _default_manager
