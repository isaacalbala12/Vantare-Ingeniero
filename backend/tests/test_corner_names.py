"""Tests corner names (Wave 6 — Task 21)."""

from src.intelligence.corner_names import distance_to_corner_name, format_lap_distance


def test_spa_blanchimont():
    assert distance_to_corner_name("Spa-Francorchamps", 4500) == "Blanchimont"


def test_format_lap_distance_fallback():
    assert "km" in format_lap_distance("Unknown", 4500)
