from src.intelligence.crewchief_events.lap_edge import (
    lap_completed,
    normalize_display_sector,
    read_sector,
)


def test_lap_completed_on_lap_number_increase():
    assert lap_completed({"lap_number": 5}, {"lap_number": 6}) is True
    assert lap_completed({"lap_number": 5}, {"lap_number": 5}) is False


def test_normalize_lmu_sector():
    assert normalize_display_sector(0) == 3
    assert normalize_display_sector(1) == 1
    assert normalize_display_sector(2) == 2


def test_read_sector_prefers_current_sector():
    assert read_sector({"current_sector": 2, "sector": 1}) == 2
