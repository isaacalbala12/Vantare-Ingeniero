"""Tests sector analysis (Wave 6 — Task 20)."""

from shared_strategy.models import SpatialDeltaPair

from src.intelligence.sector_analysis import analyze_sectors, format_sector_analysis


def test_analyze_sectors_detects_attack_and_defend():
    fuel_last = [
        SpatialDeltaPair(distance=0, value=0.0),
        SpatialDeltaPair(distance=1000, value=1.0),
        SpatialDeltaPair(distance=4500, value=2.0),
    ]
    fuel_raw = [
        SpatialDeltaPair(distance=0, value=0.0),
        SpatialDeltaPair(distance=1000, value=1.2),
        SpatialDeltaPair(distance=4500, value=1.5),
    ]
    insights = analyze_sectors(fuel_raw, fuel_last, "Spa-Francorchamps", 7004.0, threshold=0.05)
    assert insights
    recs = {i.corner_name: i.recommendation for i in insights}
    assert any(r == "defender" for r in recs.values())
    assert any(r == "atacar" for r in recs.values())


def test_format_sector_analysis_nonempty():
    insights = analyze_sectors([], [], "spa", 7000)
    assert format_sector_analysis(insights) == ""
