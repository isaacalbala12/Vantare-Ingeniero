"""Consultas de competidores — modelos y resolución determinista."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from src.intelligence.driver_names import get_driver_by_partial
from src.intelligence.time_format import format_laptime


class CompetitorQueryType(StrEnum):
    BY_NAME = "by_name"
    BY_POSITION = "by_position"
    BY_CLASS = "by_class"


class CompetitorQuery(BaseModel):
    query_type: CompetitorQueryType
    name: str | None = None
    position: int | None = None
    driver_class: str | None = None


class CompetitorResponse(BaseModel):
    found: bool
    driver_name: str = ""
    driver_class: str = ""
    standing_position: int = 0
    class_position: int = 0
    track_position: int = 0
    gap_to_player: float = 0.0
    best_lap: float = 0.0
    average_lap: float = 0.0
    in_pits: bool = False
    num_pit_stops: int = 0
    summary: str = ""


def _pace_to_dict(pace: Any) -> dict:
    if hasattr(pace, "model_dump"):
        return pace.model_dump()
    return dict(pace) if isinstance(pace, dict) else {}


def _format_gap(gap: float) -> str:
    if abs(gap) < 0.05:
        return "contigo"
    sign = "+" if gap > 0 else ""
    return f"{sign}{gap:.1f}s"


def _build_summary(data: dict) -> str:
    name = data.get("driver_name", "Desconocido")
    pos = data.get("standing_position", 0)
    cls = data.get("driver_class", "")
    gap = _format_gap(float(data.get("gap_to_player", 0)))
    best = format_laptime(float(data.get("best_lap", 0)))
    pits = " en boxes" if data.get("in_pits") else ""
    return f"{name} ({cls}) P{pos}, gap {gap}, mejor vuelta {best}{pits}."


def query_by_name(name: str, competitors: list[Any]) -> CompetitorResponse:
    drivers = [_pace_to_dict(c) for c in competitors]
    match = get_driver_by_partial(name, drivers)
    if not match:
        return CompetitorResponse(found=False, summary=f"No encuentro a '{name}' en pista.")
    return CompetitorResponse(
        found=True,
        driver_name=match.get("driver_name", ""),
        driver_class=match.get("driver_class", ""),
        standing_position=int(match.get("standing_position", 0)),
        class_position=int(match.get("class_position", 0)),
        track_position=int(match.get("track_position", 0)),
        gap_to_player=float(match.get("gap_to_player", 0)),
        best_lap=float(match.get("best_lap", 0)),
        average_lap=float(match.get("average_lap", 0)),
        in_pits=bool(match.get("in_pits", False)),
        num_pit_stops=int(match.get("num_pit_stops", 0)),
        summary=_build_summary(match),
    )


def query_by_position(position: int, competitors: list[Any]) -> CompetitorResponse:
    for c in competitors:
        data = _pace_to_dict(c)
        if int(data.get("standing_position", 0)) == position:
            return CompetitorResponse(
                found=True,
                driver_name=data.get("driver_name", ""),
                driver_class=data.get("driver_class", ""),
                standing_position=position,
                class_position=int(data.get("class_position", 0)),
                track_position=int(data.get("track_position", 0)),
                gap_to_player=float(data.get("gap_to_player", 0)),
                best_lap=float(data.get("best_lap", 0)),
                average_lap=float(data.get("average_lap", 0)),
                in_pits=bool(data.get("in_pits", False)),
                num_pit_stops=int(data.get("num_pit_stops", 0)),
                summary=_build_summary(data),
            )
    return CompetitorResponse(found=False, summary=f"Nadie en posición {position}.")


def query_class(driver_class: str, competitors: list[Any]) -> CompetitorResponse:
    from shared_strategy.competitors import filter_by_class, get_nearest_in_class

    paces = competitors
    try:
        from shared_strategy.models import CompetitorPace

        paces = [CompetitorPace(**_pace_to_dict(c)) if isinstance(c, dict) else c for c in competitors]
    except Exception:
        pass

    nearest = get_nearest_in_class(paces, driver_class)
    if nearest is None:
        filtered = filter_by_class(paces, driver_class) if paces else []
        count = len(filtered)
        if count == 0:
            return CompetitorResponse(found=False, summary=f"Sin rivales de clase {driver_class}.")
        return CompetitorResponse(
            found=True,
            summary=f"{count} coches {driver_class} en pista.",
        )

    data = _pace_to_dict(nearest)
    return CompetitorResponse(
        found=True,
        driver_name=data.get("driver_name", ""),
        driver_class=data.get("driver_class", ""),
        standing_position=int(data.get("standing_position", 0)),
        class_position=int(data.get("class_position", 0)),
        track_position=int(data.get("track_position", 0)),
        gap_to_player=float(data.get("gap_to_player", 0)),
        best_lap=float(data.get("best_lap", 0)),
        average_lap=float(data.get("average_lap", 0)),
        in_pits=bool(data.get("in_pits", False)),
        num_pit_stops=int(data.get("num_pit_stops", 0)),
        summary=_build_summary(data),
    )


def resolve_query(query: CompetitorQuery, competitors: list[Any]) -> CompetitorResponse:
    if query.query_type == CompetitorQueryType.BY_NAME and query.name:
        return query_by_name(query.name, competitors)
    if query.query_type == CompetitorQueryType.BY_POSITION and query.position:
        return query_by_position(query.position, competitors)
    if query.query_type == CompetitorQueryType.BY_CLASS and query.driver_class:
        return query_class(query.driver_class, competitors)
    return CompetitorResponse(found=False, summary="Consulta de rival incompleta.")


def resolve_from_tool_args(args: dict[str, Any], competitors: list[Any]) -> CompetitorResponse:
    query_type = args.get("query_type", "by_name")
    try:
        qtype = CompetitorQueryType(query_type)
    except ValueError:
        qtype = CompetitorQueryType.BY_NAME
    query = CompetitorQuery(
        query_type=qtype,
        name=args.get("name"),
        position=args.get("position"),
        driver_class=args.get("driver_class"),
    )
    return resolve_query(query, competitors)
