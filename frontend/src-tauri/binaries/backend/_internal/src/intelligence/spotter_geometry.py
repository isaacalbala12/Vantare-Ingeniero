"""Geometría lateral para detección car-left / car-right del spotter."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

# Mitad de longitud de coche por defecto (spotterCarLengthM=4.5 m).
SIDE_BY_SIDE_LONGITUDINAL_HALF_M = 2.25
_PATH_LONGITUDINAL_WINDOW_EXTRA_M = 2.0
_PATH_CONFIDENT_LATERAL_M = 0.8


def _wrap_lap_distance_delta(player_dist: float, comp_dist: float, track_length_m: float) -> float:
    """Delta longitudinal en m con wrap en meta/línea de salida."""
    d = float(comp_dist) - float(player_dist)
    if track_length_m <= 0:
        return d
    half = track_length_m * 0.5
    while d > half:
        d -= track_length_m
    while d < -half:
        d += track_length_m
    return d


@dataclass(frozen=True)
class LateralProximity:
    driver_index: int
    driver_class: str
    driver_name: str
    lateral_m: float
    side: str  # "izquierda" | "derecha"
    distance_m: float
    longitudinal_m: float = 0.0
    closing_mps: float = 0.0


def _normalize_xz(x: float, z: float) -> tuple[float, float]:
    mag = math.hypot(x, z)
    if mag < 0.01:
        return 0.0, 1.0
    return x / mag, z / mag


def _class_speed_rank(class_name: str) -> int:
    key = (class_name or "").lower()
    if "hyper" in key or "lmh" in key:
        return 0
    if "lmp2" in key:
        return 1
    if "lmp3" in key:
        return 2
    if "gt3" in key:
        return 3
    if "gte" in key:
        return 4
    return 5


def build_proximity_message(
    player_class: str,
    comp_class: str,
    comp_name: str,
    side: str,
) -> str:
    """Genera mensaje en español según relación de clases."""
    player_rank = _class_speed_rank(player_class)
    comp_rank = _class_speed_rank(comp_class)
    class_label = comp_class or comp_name or "Coche"

    if player_rank == comp_rank or comp_rank >= 5 or player_rank >= 5:
        return f"Coche a la {side}"
    if comp_rank < player_rank:
        return f"{class_label} doblando por la {side}"
    return f"{class_label} adelantando por la {side}"


def detect_lateral_proximity(
    player_pos: tuple[float, float, float],
    player_vel: tuple[float, float, float],
    competitors: list[dict],
    threshold_m: float,
    *,
    exclude_indices: set[int] | None = None,
) -> list[LateralProximity]:
    """Detecta rivales dentro del umbral lateral respecto al vector de marcha."""
    px, _, pz = player_pos
    vx, _, vz = player_vel
    fwd_x, fwd_z = _normalize_xz(vx, vz)
    right_x, right_z = fwd_z, -fwd_x
    exclude = exclude_indices or set()
    hits: list[LateralProximity] = []

    for comp in competitors:
        idx = int(comp.get("driver_index", -1))
        if idx in exclude:
            continue
        cx = float(comp.get("pos_x", 0.0))
        cz = float(comp.get("pos_z", 0.0))
        dx = cx - px
        dz = cz - pz
        distance = math.hypot(dx, dz)
        if distance > threshold_m * 2.5:
            continue
        lateral = dx * right_x + dz * right_z
        lateral_abs = abs(lateral)
        if lateral_abs > threshold_m:
            continue
        if distance < 0.5:
            continue
        longitudinal = dx * fwd_x + dz * fwd_z
        side = "derecha" if lateral > 0 else "izquierda"
        hits.append(
            LateralProximity(
                driver_index=idx,
                driver_class=str(comp.get("driver_class", "")),
                driver_name=str(comp.get("driver_name", "")),
                lateral_m=lateral_abs,
                side=side,
                distance_m=distance,
                longitudinal_m=longitudinal,
            )
        )
    hits.sort(key=lambda h: h.distance_m)
    return hits


def detect_path_lateral_proximity(
    player_lap: int,
    player_lap_distance: float,
    player_path_lateral: float,
    competitors: list[dict],
    threshold_m: float,
    *,
    exclude_indices: set[int] | None = None,
    invert_lateral: bool = False,
    track_length_m: float = 0.0,
    player_speed_ms: float = 0.0,
    car_length_m: float = 5.0,
) -> list[LateralProximity]:
    """Detección lateral usando path_lateral + lap_distance (telemetría LMU)."""
    exclude = exclude_indices or set()
    hits: list[LateralProximity] = []
    # Ventana longitudinal adaptada a velocidad (misma idea que cartesian_spotter).
    speed_margin = max(float(player_speed_ms), 8.0) * 0.05 * 3.5
    long_half = car_length_m / 2.0 + 2.0 + speed_margin
    long_window = long_half + threshold_m * 0.5
    track_len = track_length_m if track_length_m > 100.0 else 7000.0

    for comp in competitors:
        idx = int(comp.get("driver_index", -1))
        if idx in exclude:
            continue

        comp_lat = float(comp.get("path_lateral", 0.0))
        comp_dist = float(comp.get("lap_distance", player_lap_distance))
        longitudinal = _wrap_lap_distance_delta(player_lap_distance, comp_dist, track_len)
        if abs(longitudinal) > long_window:
            continue

        lateral_delta = comp_lat - float(player_path_lateral)
        if invert_lateral:
            lateral_delta = -lateral_delta
        lateral_abs = abs(lateral_delta)
        if lateral_abs > threshold_m:
            continue

        side = "derecha" if lateral_delta > 0 else "izquierda"
        distance = math.hypot(longitudinal, lateral_abs)
        hits.append(
            LateralProximity(
                driver_index=idx,
                driver_class=str(comp.get("driver_class", "")),
                driver_name=str(comp.get("driver_name", "")),
                lateral_m=lateral_abs,
                side=side,
                distance_m=distance,
                longitudinal_m=longitudinal,
            )
        )

    hits.sort(key=lambda h: (abs(h.longitudinal_m), h.lateral_m, h.distance_m))
    return hits


def resolve_proximity_side(
    path: Optional[LateralProximity],
    cart: Optional[LateralProximity],
    vel: Optional[LateralProximity],
    default: str,
) -> str:
    """Elige lado fiable cuando path y cartesian difieren."""
    if path is not None and path.lateral_m >= _PATH_CONFIDENT_LATERAL_M:
        return path.side

    votes: dict[str, float] = {}
    for hit in (cart, vel):
        if hit is None:
            continue
        votes[hit.side] = votes.get(hit.side, 0.0) + hit.lateral_m
    if votes:
        return max(votes, key=lambda side: votes[side])

    if path is not None:
        return path.side
    return default
