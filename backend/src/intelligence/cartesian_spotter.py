"""Detección de proximidad lateral estilo Crew Chief (coordenadas XYZ en frame local)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from shared_strategy.vehicle_lookup import get_vehicle_width


@dataclass(frozen=True)
class LocalOverlapHit:
    driver_index: int
    driver_class: str
    driver_name: str
    lateral_m: float
    longitudinal_m: float
    side: str
    overlap_score: float
    distance_m: float


def _normalize_xz(x: float, z: float) -> tuple[float, float]:
    mag = math.hypot(x, z)
    if mag < 0.01:
        return 0.0, 1.0
    return x / mag, z / mag


def lateral_offset_to_side(lateral: float, *, invert: bool = False) -> str:
    """Convierte offset lateral (+ = derecha en convención sim) a etiqueta español."""
    if invert:
        lateral = -lateral
    return "derecha" if lateral > 0 else "izquierda"


def resolve_player_forward_xz(
    ori_fwd_x: float,
    ori_fwd_z: float,
    vel_x: float,
    vel_z: float,
    last_forward: Optional[tuple[float, float]] = None,
) -> tuple[float, float]:
    if math.hypot(ori_fwd_x, ori_fwd_z) > 0.1:
        fwd_x, fwd_z = _normalize_xz(ori_fwd_x, ori_fwd_z)
    elif math.hypot(vel_x, vel_z) > 0.5:
        fwd_x, fwd_z = _normalize_xz(vel_x, vel_z)
    elif last_forward is not None:
        return last_forward
    else:
        return 0.0, 1.0
    # Alinear forward con velocidad si mOri apunta ~opuesto (evita laterales invertidos)
    if math.hypot(vel_x, vel_z) > 2.0:
        dot = fwd_x * vel_x + fwd_z * vel_z
        if dot < 0:
            fwd_x, fwd_z = -fwd_x, -fwd_z
    return fwd_x, fwd_z


def _comp_half_width(comp: dict, default: float) -> float:
    vehicle = str(comp.get("vehicle_name", "") or comp.get("driver_class", ""))
    cls = str(comp.get("driver_class", ""))
    return get_vehicle_width(vehicle, default) / 2.0


def _longitudinal_half_window(
    player_speed_ms: float,
    car_length_m: float,
    *,
    tick_dt: float = 0.05,
    ticks_margin: float = 2.5,
) -> float:
    """Ventana longitudinal adaptada a velocidad (evita perder rivales entre ticks a 20Hz)."""
    speed_margin = max(player_speed_ms, 8.0) * tick_dt * ticks_margin
    return car_length_m / 2.0 + 2.0 + speed_margin


def detect_cartesian_overlap(
    player_pos: tuple[float, float, float],
    player_forward_xz: tuple[float, float],
    competitors: list[dict],
    *,
    lateral_threshold_m: float,
    player_half_width_m: float = 1.0,
    car_length_m: float = 5.0,
    longitudinal_window_m: Optional[float] = None,
    player_speed_ms: float = 0.0,
    invert_lateral: bool = False,
    exclude_indices: Optional[set[int]] = None,
) -> list[LocalOverlapHit]:
    """Detecta rivales en overlap lateral usando frame local del jugador."""
    px, _, pz = player_pos
    fwd_x, fwd_z = _normalize_xz(player_forward_xz[0], player_forward_xz[1])
    right_x, right_z = fwd_z, -fwd_x
    exclude = exclude_indices or set()

    long_half = (
        longitudinal_window_m / 2.0
        if longitudinal_window_m is not None
        else _longitudinal_half_window(player_speed_ms, car_length_m)
    )
    long_margin = 1.0

    hits: list[LocalOverlapHit] = []
    for comp in competitors:
        idx = int(comp.get("driver_index", -1))
        if idx in exclude or idx < 0:
            continue

        cx = float(comp.get("pos_x", 0.0))
        cz = float(comp.get("pos_z", 0.0))
        dx = cx - px
        dz = cz - pz
        distance = math.hypot(dx, dz)
        if distance < 0.3:
            continue

        longitudinal = dx * fwd_x + dz * fwd_z
        lateral = dx * right_x + dz * right_z
        lateral_abs = abs(lateral)

        comp_half = _comp_half_width(comp, player_half_width_m * 2.0)
        lateral_limit = lateral_threshold_m + player_half_width_m + comp_half

        if lateral_abs > lateral_limit:
            continue
        if longitudinal < -(long_half + long_margin) or longitudinal > (long_half + long_margin):
            continue

        side = lateral_offset_to_side(lateral, invert=invert_lateral)
        overlap_score = lateral_abs + abs(longitudinal) * 0.1
        hits.append(
            LocalOverlapHit(
                driver_index=idx,
                driver_class=str(comp.get("driver_class", "")),
                driver_name=str(comp.get("driver_name", "")),
                lateral_m=lateral_abs,
                longitudinal_m=longitudinal,
                side=side,
                overlap_score=overlap_score,
                distance_m=distance,
            )
        )

    hits.sort(key=lambda h: (h.overlap_score, h.distance_m))
    return hits


def local_hit_to_lateral_proximity(hit: LocalOverlapHit):
    """Adapta LocalOverlapHit al tipo LateralProximity usado por el spotter."""
    from src.intelligence.spotter_geometry import LateralProximity

    return LateralProximity(
        driver_index=hit.driver_index,
        driver_class=hit.driver_class,
        driver_name=hit.driver_name,
        lateral_m=hit.lateral_m,
        side=hit.side,
        distance_m=hit.distance_m,
    )
