import pytest
from src.services.number_reader import SpanishNumberReader


@pytest.fixture
def r():
    return SpanishNumberReader()


class TestReadInteger:
    def test_zero(self, r):
        assert r.read_integer(0) == "cero"

    def test_units(self, r):
        assert r.read_integer(5) == "cinco"

    def test_teens(self, r):
        assert r.read_integer(15) == "quince"

    def test_tens(self, r):
        assert r.read_integer(30) == "treinta"

    def test_tens_and_unit(self, r):
        assert r.read_integer(42) == "cuarenta y dos"

    def test_veinti(self, r):
        assert r.read_integer(23) == "veintitres"

    def test_hundreds(self, r):
        assert r.read_integer(200) == "doscientos"

    def test_hundreds_and_rest(self, r):
        assert r.read_integer(342) == "trescientos cuarenta y dos"

    def test_negative(self, r):
        assert "menos" in r.read_integer(-7)


class TestReadTime:
    def test_minutes(self, r):
        result = r.read_time(90, "MINUTES")
        assert "minuto" in result or "minutos" in result

    def test_tenths(self, r):
        result = r.read_time(2.5, "TENTHS")
        assert "décimas" in result

    def test_seconds(self, r):
        result = r.read_time(45.0, "SECONDS")
        assert "segundos" in result

    def test_auto_laptimes_with_minutes(self, r):
        result = r.read_time(92.5, "AUTO_LAPTIMES")
        assert "uno" in result

    def test_hundredths(self, r):
        result = r.read_time(0.45, "HUNDREDTHS")
        assert "centésimas" in result

    def test_auto_gaps_seconds(self, r):
        result = r.read_time(15.0, "AUTO_GAPS")
        assert "segundos" in result

    def test_auto_gaps_tenths(self, r):
        result = r.read_time(3.2, "AUTO_GAPS")
        assert "décimas" in result


class TestReadGap:
    def test_gap_tenths(self, r):
        result = r.read_gap(2.5)
        assert "décimas" in result

    def test_gap_seconds(self, r):
        result = r.read_gap(12.0)
        assert "segundos" in result

    def test_gap_minutes(self, r):
        result = r.read_gap(90.0)
        assert "minutos" in result
