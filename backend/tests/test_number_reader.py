"""Tests del NumberReader — lectura de números y tiempos en castellano.

Cobertura:
- read_integer: 0-999, negativos, miles
- read_time: todas las precisiones, casos borde
- read_gap: subdivisión de minutos/segundos/décimas
"""
import pytest
from src.services.number_reader import (
    SpanishNumberReader, NumberReader,
    PRECISION_AUTO_LAPTIMES, PRECISION_AUTO_GAPS,
    PRECISION_SECONDS, PRECISION_TENTHS,
    PRECISION_HUNDREDTHS, PRECISION_MINUTES,
)


@pytest.fixture
def r():
    return SpanishNumberReader()


# =========================================================
# read_integer
# =========================================================
class TestReadInteger:
    def test_zero(self, r):
        assert r.read_integer(0) == "cero"

    def test_units(self, r):
        assert r.read_integer(1) == "uno"
        assert r.read_integer(5) == "cinco"
        assert r.read_integer(9) == "nueve"

    def test_teens(self, r):
        assert r.read_integer(10) == "diez"
        assert r.read_integer(11) == "once"
        assert r.read_integer(15) == "quince"
        assert r.read_integer(19) == "diecinueve"

    def test_tens(self, r):
        assert r.read_integer(20) == "veinte"
        assert r.read_integer(30) == "treinta"
        assert r.read_integer(50) == "cincuenta"
        assert r.read_integer(90) == "noventa"

    def test_veinti_compound(self, r):
        assert r.read_integer(21) == "veintiuno"
        assert r.read_integer(23) == "veintitres"

    def test_tens_and_unit(self, r):
        assert r.read_integer(42) == "cuarenta y dos"
        assert r.read_integer(77) == "setenta y siete"

    def test_hundreds(self, r):
        assert r.read_integer(100) == "cien"
        assert r.read_integer(200) == "doscientos"
        assert r.read_integer(500) == "quinientos"
        assert r.read_integer(900) == "novecientos"

    def test_hundreds_and_rest(self, r):
        assert r.read_integer(342) == "trescientos cuarenta y dos"

    def test_thousands(self, r):
        assert r.read_integer(1000) == "uno mil"
        assert r.read_integer(2500) == "dos mil quinientos"

    def test_negative(self, r):
        assert "menos" in r.read_integer(-7)
        assert "siete" in r.read_integer(-7)


# =========================================================
# read_time
# =========================================================
class TestReadTime:
    def test_minutes_precision_one(self, r):
        result = r.read_time(60, PRECISION_MINUTES)
        assert "minuto" in result

    def test_minutes_precision_zero(self, r):
        result = r.read_time(0, PRECISION_MINUTES)
        assert "cero" in result or "0" in result

    def test_minutes_precision_multiple(self, r):
        result = r.read_time(180, PRECISION_MINUTES)
        assert "tres minutos" in result

    def test_tenths_precision(self, r):
        result = r.read_time(2.5, PRECISION_TENTHS)
        assert "veinticinco" in result
        assert "d" in result

    def test_seconds_precision(self, r):
        result = r.read_time(45.0, PRECISION_SECONDS)
        assert "cuarenta y cinco" in result
        assert "segundos" in result

    def test_seconds_precision_rounds(self, r):
        result = r.read_time(44.7, PRECISION_SECONDS)
        assert "cuarenta y cinco" in result

    def test_hundredths_precision(self, r):
        result = r.read_time(0.45, PRECISION_HUNDREDTHS)
        assert "cuarenta y cinco" in result or "45" in result

    def test_auto_laptimes_simple(self, r):
        """P2 fix: 92.5s debe leerse como 'uno, treinta y dos, quinientos' (no '3250 centésimas')."""
        result = r.read_time(92.5, PRECISION_AUTO_LAPTIMES)
        assert "uno" in result
        assert "treinta y dos" in result
        assert "quinientos" in result
        # NO debe decir "centésimas" porque estamos en minutos
        assert "cent" not in result

    def test_auto_laptimes_exact(self, r):
        result = r.read_time(90.0, PRECISION_AUTO_LAPTIMES)
        assert "uno" in result
        assert "treinta" in result

    def test_auto_laptimes_no_minutes(self, r):
        """< 60s: solo segundos y milisegundos."""
        result = r.read_time(45.3, PRECISION_AUTO_LAPTIMES)
        assert "cuarenta y cinco" in result
        assert "trescientos" in result

    def test_auto_laptimes_sub_second(self, r):
        result = r.read_time(0.450, PRECISION_AUTO_LAPTIMES)
        assert "cero" in result
        assert "cuatrocientos cincuenta" in result

    def test_auto_gaps_with_minutes(self, r):
        result = r.read_time(90.0, PRECISION_AUTO_GAPS)
        assert "minuto" in result

    def test_auto_gaps_seconds(self, r):
        result = r.read_time(15.0, PRECISION_AUTO_GAPS)
        assert "quince" in result
        assert "segundos" in result

    def test_auto_gaps_tenths(self, r):
        result = r.read_time(3.2, PRECISION_AUTO_GAPS)
        assert "treinta y dos" in result or "32" in result

    def test_negative_time(self, r):
        result = r.read_time(-10.0, PRECISION_SECONDS)
        assert "menos" in result


# =========================================================
# read_gap
# =========================================================
class TestReadGap:
    def test_tenths(self, r):
        result = r.read_gap(2.5)
        assert "veinticinco" in result
        assert "d" in result

    def test_seconds(self, r):
        result = r.read_gap(12.0)
        assert "doce" in result
        assert "segundos" in result

    def test_one_minute(self, r):
        result = r.read_gap(60.0)
        assert "un minuto" in result
        # Sin "cero" ni décimas cuando los segundos son 0
        assert "cero" not in result

    def test_minute_and_seconds(self, r):
        result = r.read_gap(90.0)
        assert "un minuto" in result
        assert "treinta segundos" in result

    def test_two_minutes(self, r):
        result = r.read_gap(120.0)
        assert "dos minutos" in result
        assert "cero" not in result

    def test_minutes_with_seconds(self, r):
        result = r.read_gap(130.5)
        assert "dos minutos" in result
        assert "diez" in result
        assert "segundos" in result

    def test_negative_gap(self, r):
        result = r.read_gap(-5.0)
        assert "menos" in result

    def test_zero_gap(self, r):
        result = r.read_gap(0.0)
        assert result == "cero"


# =========================================================
# Interfaz extensible
# =========================================================
class TestExtensibility:
    def test_base_class_methods_not_implemented(self):
        """Las clases base lanzan NotImplementedError."""
        base = NumberReader()
        with pytest.raises(NotImplementedError):
            base.read_integer(5)
        with pytest.raises(NotImplementedError):
            base.read_time(5.0)
        with pytest.raises(NotImplementedError):
            base.read_gap(5.0)
