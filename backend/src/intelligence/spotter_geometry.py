"""Geometría lateral para detección car-left / car-right del spotter."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LateralProximity:
    driver_index: int
    driver_class: str
    driver_name: str
    lateral_m: float
    side: str  # "izquierda" | "derecha"
    distance_m: float


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
    exclude_indices: Optional[set[int]] = None,
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
        side = "derecha" if lateral > 0 else "izquierda"
        hits.append(
            LateralProximity(
                driver_index=idx,
                driver_class=str(comp.get("driver_class", "")),
                driver_name=str(comp.get("driver_name", "")),
                lateral_m=lateral_abs,
                side=side,
                distance_m=distance,
            )
        )
    hits.sort(key=lambda h: h.distance_m)
    return hits
