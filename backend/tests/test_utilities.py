"""Tests del módulo utilities — random, WholeAndFractionalPart, InterruptedSleep.

Cobertura:
- random_int: rango, reproducibilidad con seed
- random_double: rango [0, 1)
- WholeAndFractionalPart: enteros, fracciones, negativos, decimales custom
- set_random_seed: reproducibilidad
"""
import pytest
import time
from threading import Thread
from src.services.utilities import (
    random_int, random_double, WholeAndFractionalPart,
    set_random_seed,
)


class TestRandom:
    def test_random_int_in_range(self):
        for _ in range(50):
            v = random_int(5, 10)
            assert 5 <= v <= 10

    def test_random_int_zero_range(self):
        """min == max siempre devuelve ese valor."""
        for _ in range(10):
            assert random_int(7, 7) == 7

    def test_random_double_in_range(self):
        for _ in range(50):
            v = random_double()
            assert 0.0 <= v < 1.0


class TestSeedReproducibility:
    def test_same_seed_same_sequence(self):
        set_random_seed(42)
        seq1 = [random_int(1, 1000) for _ in range(10)]
        set_random_seed(42)
        seq2 = [random_int(1, 1000) for _ in range(10)]
        assert seq1 == seq2

    def test_different_seeds_different_sequences(self):
        set_random_seed(1)
        seq1 = [random_int(1, 1000) for _ in range(5)]
        set_random_seed(2)
        seq2 = [random_int(1, 1000) for _ in range(5)]
        assert seq1 != seq2

    def test_seed_zero_works(self):
        set_random_seed(0)
        assert isinstance(random_int(1, 100), int)


class TestWholeAndFractionalPart:
    def test_whole_number(self):
        w, f = WholeAndFractionalPart(5.0, 1)
        assert w == 5
        assert f == 0

    def test_with_fraction(self):
        w, f = WholeAndFractionalPart(3.5, 1)
        assert w == 3
        assert f == 5

    def test_with_two_decimals(self):
        w, f = WholeAndFractionalPart(3.75, 2)
        assert w == 3
        assert f == 75

    def test_negative_value(self):
        """Bug fix: floor division no debe aplicarse a negativos."""
        w, f = WholeAndFractionalPart(-2.75, 2)
        assert w == -2
        assert f == 75

    def test_negative_integer(self):
        w, f = WholeAndFractionalPart(-5.0, 1)
        assert w == -5
        assert f == 0

    def test_negative_with_half(self):
        w, f = WholeAndFractionalPart(-2.5, 1)
        # -2.5 → whole=-2, frac=50 (o -50 según convención)
        # Nuestro fix da abs para frac
        assert w == -2
        assert f == 50

    def test_custom_decimal_places(self):
        w, f = WholeAndFractionalPart(1.234, 3)
        assert w == 1
        assert f == 234

    def test_zero(self):
        w, f = WholeAndFractionalPart(0.0, 2)
        assert w == 0
        assert f == 0

    def test_rounding(self):
        """3.555 con 2 decimales debe redondear a 3.56, no truncar a 3.55."""
        w, f = WholeAndFractionalPart(3.555, 2)
        # 3.555 * 100 = 355.5, round() = 356
        assert w == 3
        assert f == 56

    def test_returns_integers(self):
        """El retorno debe ser enteros (no floats)."""
        w, f = WholeAndFractionalPart(3.5, 1)
        assert isinstance(w, int)
        assert isinstance(f, int)
