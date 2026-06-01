"""Transformaciones de coordenadas cartesianas para el spotter.

aligned_xz(yaw, px, pz, ox, oz) devuelve (ax, az) — las coordenadas del
oponente relativas al piloto, con el piloto mirando hacia +Z local.
"""
import math
from typing import Tuple


def aligned_xz(
    yaw: float, px: float, pz: float, ox: float, oz: float
) -> Tuple[float, float]:
    """Rota el vector (ox-px, oz-pz) por -yaw para obtener coords locales.

    Convención: piloto mira hacia +Z en su frame local.
    - ax positivo: oponente a la DERECHA
    - ax negativo: oponente a la IZQUIERDA
    - az positivo: oponente DELANTE
    - az negativo: oponente DETRÁS
    """
    dx = ox - px
    dz = oz - pz
    c = math.cos(-yaw)
    s = math.sin(-yaw)
    return (dx * c - dz * s, dx * s + dz * c)
