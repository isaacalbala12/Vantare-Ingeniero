"""Tests consultas de competidores (Wave 5 — Task 15)."""

from shared_strategy.models import CompetitorPace

from src.intelligence.competitor_queries import (
    CompetitorQuery,
    CompetitorQueryType,
    query_by_name,
    query_by_position,
    query_class,
    resolve_query,
)


def _sample_competitors() -> list[CompetitorPace]:
    return [
        CompetitorPace(
            driver_index=1,
            driver_name="Sergio Pérez",
            driver_class="Hypercar",
            standing_position=3,
            class_position=2,
            gap_to_player=2.1,
            best_lap=108.2,
            average_lap=109.0,
            estimated_stint_length=30,
            num_pit_stops=1,
            in_pits=False,
        ),
        CompetitorPace(
            driver_index=2,
            driver_name="Kevin Magnussen",
            driver_class="GT3",
            standing_position=12,
            class_position=4,
            gap_to_player=-1.5,
            best_lap=112.0,
            average_lap=113.2,
            estimated_stint_length=25,
            num_pit_stops=0,
            in_pits=False,
        ),
    ]


def test_query_by_name_fuzzy():
    result = query_by_name("Perez", _sample_competitors())
    assert result.found
    assert "Pérez" in result.driver_name
    assert "P3" in result.summary or "P3" in result.summary.replace(" ", "")


def test_query_by_position():
    result = query_by_position(12, _sample_competitors())
    assert result.found
    assert result.driver_name == "Kevin Magnussen"


def test_query_class_nearest():
    result = query_class("GT3", _sample_competitors())
    assert result.found
    assert "Magnussen" in result.driver_name or "Magnussen" in result.summary


def test_resolve_query_by_name():
    q = CompetitorQuery(query_type=CompetitorQueryType.BY_NAME, name="Magnussen")
    result = resolve_query(q, _sample_competitors())
    assert result.found
