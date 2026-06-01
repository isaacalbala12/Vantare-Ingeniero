import pytest
from src.services.track_definition import (
    TrackLengthClass, get_length_class, TrackDefinition,
    FUEL_WINDOW_LENGTH, LAPS_BEFORE_GAPS, OUTLIER_PACE_LIMITS
)

def test_very_long():
    assert get_length_class(25000) == TrackLengthClass.VERY_LONG

def test_long():
    assert get_length_class(15000) == TrackLengthClass.LONG

def test_medium():
    assert get_length_class(5000) == TrackLengthClass.MEDIUM

def test_short():
    assert get_length_class(1500) == TrackLengthClass.SHORT

def test_very_short():
    assert get_length_class(500) == TrackLengthClass.VERY_SHORT

def test_track_definition_auto_gap_points():
    td = TrackDefinition(name="Test", track_length=5000)
    assert len(td.gap_points) > 0
    assert td.gap_points[-1] > 3000

def test_track_definition_oval():
    td = TrackDefinition(name="Oval", track_length=2000, is_oval=True)
    assert td.is_oval

def test_fuel_window_very_long():
    assert FUEL_WINDOW_LENGTH[TrackLengthClass.VERY_LONG] == 1

def test_laps_before_gaps_short():
    assert LAPS_BEFORE_GAPS[TrackLengthClass.SHORT] == 3

def test_outlier_limits():
    assert OUTLIER_PACE_LIMITS[TrackLengthClass.LONG] == 8
