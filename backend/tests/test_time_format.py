"""Tests para time_format coloquial."""

from src.intelligence.time_format import format_fuel, format_laptime, format_time_remaining


def test_laptime_under_60_seconds():
    assert format_laptime(26.5) == "26.5"


def test_laptime_over_60_seconds():
    assert format_laptime(92.5) == "1:32.5"


def test_time_remaining_two_hours():
    assert format_time_remaining(7200) == "2 horas"


def test_time_remaining_half_hour():
    assert format_time_remaining(1800) == "media hora"


def test_fuel_colloquial():
    assert format_fuel(26.5) == "26 punto 5"
    assert format_fuel(120) == "ciento veinte"
