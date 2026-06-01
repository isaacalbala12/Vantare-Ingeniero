"""Tests del TrackDefinition — clasificación automática de circuitos.

Cobertura:
- get_length_class: cada categoría (VERY_SHORT a VERY_LONG)
- TrackDefinition: gap_points automáticos, oval flag
- Diccionarios de configuración: FUEL_WINDOW_LENGTH, LAPS_BEFORE_GAPS, OUTLIER_PACE_LIMITS
"""
import pytest
from src.services.track_definition import (
    TrackLengthClass, get_length_class, TrackDefinition,
    FUEL_WINDOW_LENGTH, LAPS_BEFORE_GAPS, OUTLIER_PACE_LIMITS,
)


class TestLengthClassification:
    def test_very_long_threshold(self):
        assert get_length_class(25000) == TrackLengthClass.VERY_LONG

    def test_very_long_boundary(self):
        assert get_length_class(20001) == TrackLengthClass.VERY_LONG
        assert get_length_class(20000) == TrackLengthClass.LONG

    def test_long_range(self):
        assert get_length_class(15000) == TrackLengthClass.LONG
        assert get_length_class(10001) == TrackLengthClass.LONG

    def test_medium_range(self):
        assert get_length_class(5000) == TrackLengthClass.MEDIUM
        assert get_length_class(2400) == TrackLengthClass.MEDIUM

    def test_short_range(self):
        assert get_length_class(2000) == TrackLengthClass.SHORT
        assert get_length_class(1000) == TrackLengthClass.SHORT

    def test_very_short_range(self):
        assert get_length_class(500) == TrackLengthClass.VERY_SHORT
        assert get_length_class(0) == TrackLengthClass.VERY_SHORT

    def test_zero_length(self):
        """Longitud 0 debe clasificarse como VERY_SHORT, no crashear."""
        assert get_length_class(0) == TrackLengthClass.VERY_SHORT


class TestTrackDefinition:
    def test_basic_creation(self):
        td = TrackDefinition(name="Test", track_length=5000)
        assert td.name == "Test"
        assert td.track_length == 5000

    def test_length_class_assigned(self):
        td = TrackDefinition(name="Le Mans", track_length=13500)
        assert td.track_length_class == TrackLengthClass.LONG

    def test_default_sectors(self):
        td = TrackDefinition(name="Test", track_length=5000)
        assert td.sectors == 3

    def test_oval_flag(self):
        td = TrackDefinition(name="Oval", track_length=2000, is_oval=True)
        assert td.is_oval is True

    def test_auto_gap_points_for_long_track(self):
        td = TrackDefinition(name="Test", track_length=5000)
        assert len(td.gap_points) > 0
        # El último gap point debe estar cerca del final del circuito
        assert td.gap_points[-1] > 3000

    def test_no_auto_gap_points_for_short_track(self):
        """Circuitos cortos (<3000m) no generan gap_points automáticos."""
        td = TrackDefinition(name="Short", track_length=2500)
        # Sin gap_points iniciales, y la generación automática es para >3000
        assert td.gap_points == []

    def test_custom_gap_points_preserved(self):
        td = TrackDefinition(name="Test", track_length=5000, gap_points=[100, 200, 300])
        # Los gap_points custom se preservan y se usa length_class
        assert 100 in td.gap_points

    def test_landmarks_default_empty(self):
        td = TrackDefinition(name="Test", track_length=5000)
        assert td.landmarks == []


class TestConfigDictionaries:
    def test_fuel_window_very_long(self):
        assert FUEL_WINDOW_LENGTH[TrackLengthClass.VERY_LONG] == 1

    def test_fuel_window_very_short(self):
        assert FUEL_WINDOW_LENGTH[TrackLengthClass.VERY_SHORT] == 5

    def test_fuel_window_monotonic(self):
        """Más corto = más fuel window (más laps de aviso)."""
        values = [FUEL_WINDOW_LENGTH[cl] for cl in TrackLengthClass]
        # Debe estar en orden creciente de más corto a más largo
        # VERY_SHORT=5, SHORT=4, MEDIUM=3, LONG=2, VERY_LONG=1
        assert values == sorted(values, reverse=True)

    def test_laps_before_gaps_very_long(self):
        assert LAPS_BEFORE_GAPS[TrackLengthClass.VERY_LONG] == 0

    def test_laps_before_gaps_very_short(self):
        assert LAPS_BEFORE_GAPS[TrackLengthClass.VERY_SHORT] == 4

    def test_outlier_limits_long(self):
        assert OUTLIER_PACE_LIMITS[TrackLengthClass.LONG] == 8

    def test_outlier_limits_very_long(self):
        assert OUTLIER_PACE_LIMITS[TrackLengthClass.VERY_LONG] == 15

    def test_all_classes_have_config(self):
        for cl in TrackLengthClass:
            assert cl in FUEL_WINDOW_LENGTH
            assert cl in LAPS_BEFORE_GAPS
            assert cl in OUTLIER_PACE_LIMITS
