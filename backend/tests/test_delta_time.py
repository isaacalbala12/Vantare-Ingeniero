import pytest
from src.services.delta_time import DeltaTime


def test_delta_time_creation():
    dt = DeltaTime(90.5, 12)
    assert dt.time == 90.5
    assert dt.lap == 12


def test_signed_lap_diff_same():
    dt1 = DeltaTime(90.0, 10)
    dt2 = DeltaTime(85.0, 10)
    assert dt1.get_signed_lap_diff(dt2) == 0


def test_signed_lap_diff_ahead():
    dt1 = DeltaTime(90.0, 11)
    dt2 = DeltaTime(85.0, 10)
    assert dt1.get_signed_lap_diff(dt2) == 1


def test_signed_lap_diff_behind():
    dt1 = DeltaTime(90.0, 9)
    dt2 = DeltaTime(85.0, 10)
    assert dt1.get_signed_lap_diff(dt2) == -1


def test_absolute_time_delta_same_lap():
    dt1 = DeltaTime(92.0, 10)
    dt2 = DeltaTime(90.0, 10)
    ld, td = dt1.get_absolute_time_delta(dt2)
    assert ld == 0
    assert td == 2.0


def test_absolute_time_delta_one_lap_ahead():
    dt1 = DeltaTime(90.0, 11)
    dt2 = DeltaTime(85.0, 10)
    ld, td = dt1.get_absolute_time_delta(dt2, best_lap=90.0)
    assert ld == 1
    assert td == 95.0  # 5.0 + 1 * 90.0


def test_absolute_time_delta_no_best_lap():
    dt1 = DeltaTime(90.0, 11)
    dt2 = DeltaTime(85.0, 10)
    ld, td = dt1.get_absolute_time_delta(dt2)
    assert ld == 1
    assert td == 5.0
