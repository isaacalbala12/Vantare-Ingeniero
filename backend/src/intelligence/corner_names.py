"""Traducción distancia → nombre de curva para mensajes LLM/TTS."""

from __future__ import annotations

from src.intelligence.track_spline import get_track_manager


def distance_to_corner_name(track_name: str, distance_m: float) -> str:
    """Devuelve nombre de curva cercano o fallback en km."""
    mgr = get_track_manager()
    corner = mgr.get_nearest_corner(track_name, distance_m)
    if corner:
        return corner
    return f"km {distance_m / 1000:.1f}"


def format_lap_distance(track_name: str, distance_m: float) -> str:
    """Formato hablado: 'Blanchimont' o 'km 4.5'."""
    return distance_to_corner_name(track_name, distance_m)
