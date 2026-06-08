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


def _normalize_class_label(class_name: str) -> str:
    key = (class_name or "").lower()
    if "hyper" in key or "lmh" in key:
        return "Hypercar"
    if "lmp2" in key:
        return "LMP2"
    if "lmp3" in key:
        return "LMP3"
    if "gt3" in key:
        return "GT3"
    if "gte" in key:
        return "GTE"
    return class_name or "Coche"


def build_proximity_message(
    player_class: str,
    comp_class: str,
    comp_name: str,
    side: str,
) -> str:
    """Genera mensaje en español según relación de clases."""
    player_rank = _class_speed_rank(player_class)
    comp_rank = _class_speed_rank(comp_class)
    class_label = _normalize_class_label(comp_class) or comp_name or "Coche"

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
    forward_xz: Optional[tuple[float, float]] = None,
    max_distance_m: Optional[float] = None,
) -> list[LateralProximity]:
    """Detecta rivales dentro del umbral lateral respecto al vector de marcha."""
    px, _, pz = player_pos
    vx, _, vz = player_vel
    if forward_xz is not None:
        fwd_x, fwd_z = _normalize_xz(forward_xz[0], forward_xz[1])
    else:
        fwd_x, fwd_z = _normalize_xz(vx, vz)
    right_x, right_z = fwd_z, -fwd_x
    exclude = exclude_indices or set()
    hits: list[LateralProximity] = []
    distance_limit = max_distance_m if max_distance_m is not None else threshold_m * 4.0

    for comp in competitors:
        idx = int(comp.get("driver_index", -1))
        if idx in exclude:
            continue
        cx = float(comp.get("pos_x", 0.0))
        cz = float(comp.get("pos_z", 0.0))
        dx = cx - px
        dz = cz - pz
        distance = math.hypot(dx, dz)
        if distance > distance_limit:
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


def enrich_hits_with_closing_speed(
    hits: list[LateralProximity],
    player_vel: tuple[float, float, float],
    competitors: list[dict],
) -> list[LateralProximity]:
    """Añade velocidad de cierre longitudinal (m/s positivo = acercándose)."""
    comp_by_idx = {int(c.get("driver_index", -1)): c for c in competitors}
    enriched: list[LateralProximity] = []
    pvx, _, pvz = player_vel
    for hit in hits:
        comp = comp_by_idx.get(hit.driver_index)
        closing = 0.0
        if comp:
            cvx = float(comp.get("vel_x", comp.get("speed_x", 0.0)) or 0.0)
            cvz = float(comp.get("vel_z", comp.get("speed_z", 0.0)) or 0.0)
            if cvx == 0.0 and cvz == 0.0:
                cs = float(comp.get("speed", 0.0) or 0.0)
                if cs > 0:
                    cvx, cvz = cs, 0.0
            closing = max(0.0, (cvx - pvx) * 0.5 + (cvz - pvz) * 0.5)
        enriched.append(
            LateralProximity(
                driver_index=hit.driver_index,
                driver_class=hit.driver_class,
                driver_name=hit.driver_name,
                lateral_m=hit.lateral_m,
                side=hit.side,
                distance_m=hit.distance_m,
                closing_mps=closing,
            )
        )
    return enriched


def detect_path_lateral_proximity(
    player_lap: int,
    player_lap_dist: float,
    player_lateral: float,
    competitors: list[dict],
    threshold_m: float,
    *,
    along_window_m: float = 18.0,
    exclude_indices: Optional[set[int]] = None,
) -> list[LateralProximity]:
    """Detección lateral vía mPathLateral + mLapDist (datos nativos LMU scoring)."""
    exclude = exclude_indices or set()
    hits: list[LateralProximity] = []
    min_lateral = max(1.0, threshold_m * 0.35)

    for comp in competitors:
        idx = int(comp.get("driver_index", -1))
        if idx in exclude:
            continue
        comp_lap = int(comp.get("lap_number", 0))
        if abs(comp_lap - player_lap) > 0:
            continue
        comp_dist = float(comp.get("lap_distance", 0.0))
        along = abs(comp_dist - player_lap_dist)
        if along > along_window_m:
            continue
        lat_delta = float(comp.get("path_lateral", 0.0)) - player_lateral
        lat_abs = abs(lat_delta)
        if lat_abs < min_lateral or lat_abs > threshold_m:
            continue
        side = "derecha" if lat_delta > 0 else "izquierda"
        hits.append(
            LateralProximity(
                driver_index=idx,
                driver_class=str(comp.get("driver_class", "")),
                driver_name=str(comp.get("driver_name", "")),
                lateral_m=lat_abs,
                side=side,
                distance_m=along,
            )
        )
    hits.sort(key=lambda h: (h.lateral_m, h.distance_m))
    return hits
