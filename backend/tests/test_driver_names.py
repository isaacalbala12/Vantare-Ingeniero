"""Tests driver_names fuzzy matching."""

from src.intelligence.driver_names import fuzzy_match, get_driver_by_partial, normalize_name


def test_normalize_name_strips_accents():
    assert normalize_name("Pérez") == "perez"


def test_fuzzy_match_accented_name():
    result = fuzzy_match("perez", ["Pérez", "Hamilton"])
    assert result is not None
    name, score = result
    assert name == "Pérez"
    assert score > 0.8


def test_get_driver_by_partial_surname():
    drivers = [
        {"driver_name": "Fernando Alonso", "driver_index": 1},
        {"driver_name": "Lewis Hamilton", "driver_index": 2},
    ]
    found = get_driver_by_partial("alonso", drivers)
    assert found is not None
    assert found["driver_index"] == 1
