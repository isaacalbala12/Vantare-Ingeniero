"""Análisis ataque/defensa por sector usando Spatial Delta Arrays."""

from __future__ import annotations

from dataclasses import dataclass

from shared_strategy.calculation import delta_telemetry

from src.intelligence.corner_names import distance_to_corner_name


@dataclass
class SectorInsight:
    distance: float
    corner_name: str
    delta_value: float
    recommendation: str


def analyze_sectors(
    fuel_raw: list,
    fuel_last: list,
    track_name: str,
    track_length: float,
    threshold: float = 0.05,
) -> list[SectorInsight]:
    """Compara perfil de combustible actual vs vuelta de referencia por sector.

    delta_value positivo → más consumo que la referencia → perdiendo tiempo (defender).
    delta_value negativo → menos consumo → ganando tiempo (atacar).
    """
    if not fuel_raw or not fuel_last or track_length <= 0:
        return []

    from src.intelligence.track_spline import get_track_manager

    manager = get_track_manager()
    spline = manager.get(track_name)
    if spline and spline.points:
        distances = [p.distance for p in spline.points if p.is_corner]
    else:
        distances = [float(d) for d in range(500, int(track_length), 500)]

    insights: list[SectorInsight] = []
    for distance in distances:
        ref_val = delta_telemetry(fuel_last, fuel_last, distance, track_length)
        curr_val = delta_telemetry(fuel_raw, fuel_raw, distance, track_length)
        delta = curr_val - ref_val
        if abs(delta) < threshold:
            continue
        corner = distance_to_corner_name(track_name, distance)
        recommendation = "defender" if delta > 0 else "atacar"
        insights.append(
            SectorInsight(
                distance=distance,
                corner_name=corner,
                delta_value=round(delta, 3),
                recommendation=recommendation,
            )
        )
    return insights


def format_sector_analysis(insights: list[SectorInsight]) -> str:
    """Texto compacto para inyectar en prompt LLM."""
    if not insights:
        return ""
    lines = ["SECTORES (ataque/defensa vs vuelta ref):"]
    for s in insights[:6]:
        lines.append(f"- {s.corner_name}: {s.recommendation} (Δ{s.delta_value:+.2f})")
    return "\n".join(lines)
