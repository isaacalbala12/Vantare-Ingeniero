"""Tests del DeltaTime — cálculo de gaps con diferencia de vueltas (multiclase).

Cobertura:
- Construcción
- Diferencia de vueltas firmada (signed lap diff)
- Diferencia de tiempo absoluta con y sin best_lap
- Multiclase: gap incluye tiempo de vueltas de diferencia
- Casos borde: mismo lap, una vuelta de diferencia, sin best_lap
"""
import pytest
from src.services.delta_time import DeltaTime


class TestCreation:
    def test_creation(self):
        dt = DeltaTime(90.5, 12)
        assert dt.time == 90.5
        assert dt.lap == 12

    def test_fields_accessible(self):
        dt = DeltaTime(60.0, 5)
        assert dt.time == 60.0
        assert dt.lap == 5


class TestSignedLapDiff:
    def test_same_lap(self):
        dt1 = DeltaTime(90.0, 10)
        dt2 = DeltaTime(85.0, 10)
        assert dt1.get_signed_lap_diff(dt2) == 0

    def test_self_ahead(self):
        dt1 = DeltaTime(90.0, 11)
        dt2 = DeltaTime(85.0, 10)
        assert dt1.get_signed_lap_diff(dt2) == 1

    def test_self_behind(self):
        dt1 = DeltaTime(90.0, 9)
        dt2 = DeltaTime(85.0, 10)
        assert dt1.get_signed_lap_diff(dt2) == -1

    def test_multiple_laps_ahead(self):
        dt1 = DeltaTime(90.0, 15)
        dt2 = DeltaTime(85.0, 10)
        assert dt1.get_signed_lap_diff(dt2) == 5


class TestAbsoluteTimeDelta:
    def test_same_lap(self):
        dt1 = DeltaTime(92.0, 10)
        dt2 = DeltaTime(90.0, 10)
        ld, td = dt1.get_absolute_time_delta(dt2)
        assert ld == 0
        assert td == 2.0

    def test_same_lap_reversed(self):
        """El delta siempre es absoluto, sin importar el orden."""
        dt1 = DeltaTime(90.0, 10)
        dt2 = DeltaTime(92.0, 10)
        ld, td = dt1.get_absolute_time_delta(dt2)
        assert ld == 0
        assert td == 2.0  # abs(90-92) = 2

    def test_one_lap_ahead_with_best_lap(self):
        dt1 = DeltaTime(90.0, 11)
        dt2 = DeltaTime(85.0, 10)
        ld, td = dt1.get_absolute_time_delta(dt2, best_lap=90.0)
        assert ld == 1
        # 5.0 (time diff) + 1 * 90.0 (lap diff * best_lap) = 95.0
        assert td == 95.0

    def test_one_lap_ahead_without_best_lap(self):
        """Sin best_lap, el gap no incluye la vuelta extra."""
        dt1 = DeltaTime(90.0, 11)
        dt2 = DeltaTime(85.0, 10)
        ld, td = dt1.get_absolute_time_delta(dt2)
        assert ld == 1
        assert td == 5.0

    def test_one_lap_ahead_with_zero_best_lap(self):
        """best_lap=0 no debe multiplicar."""
        dt1 = DeltaTime(90.0, 11)
        dt2 = DeltaTime(85.0, 10)
        ld, td = dt1.get_absolute_time_delta(dt2, best_lap=0.0)
        assert ld == 1
        assert td == 5.0

    def test_multiclass_hypercar_vs_gt3(self):
        """Hypercar 2 vueltas por delante de un GT3."""
        dt_hyper = DeltaTime(120.0, 50)  # vuelta 50
        dt_gt3 = DeltaTime(95.0, 48)    # vuelta 48 (2 menos)
        ld, td = dt_hyper.get_absolute_time_delta(dt_gt3, best_lap=200.0)
        assert ld == 2
        # 25 (time diff) + 2 * 200 (lap diff * best_lap) = 425
        assert td == 425.0
