"""Tests unitarios para el módulo ticker.

Verifica la generación correcta del formato ticker compacto (~400 tokens)
para prompts del LLM, según las especificaciones de LMU/rag-dictionary.md.
"""

import pytest
import sys
from pathlib import Path

# Asegurar que el módulo ticker esté importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.intelligence.ticker import (
    abbreviate_name,
    generate_ticker,
    _format_drv,
    _format_brk,
    _format_gap,
    _format_ses,
    _format_wth,
    _format_riv,
    _format_time,
    _format_laptime,
)


class TestAbbreviateName:
    """Tests para abbreviate_name()."""

    def test_full_name(self):
        assert abbreviate_name("Valentino Rossi") == "VAL"

    def test_single_word_name(self):
        assert abbreviate_name("Alonso") == "ALO"

    def test_empty_name(self):
        assert abbreviate_name("") == "DRV"

    def test_driver_name(self):
        assert abbreviate_name("Driver") == "DRV"


class TestFormatDRV:
    """Tests para la línea DRV."""

    def test_full_drv_with_tyr(self):
        """DRV con todos los campos, lap > 3 debe incluir TYR."""
        data = {
            "lap": 26,
            "position": 3,
            "fuel": 42.3,
            "fuel_rate_trend": 3.2,
            "laps_rest": 13,
            "tyre_wear": [72, 68, 65, 63],
            "tyre_temps": [92, 94, 98, 96],
        }
        result = _format_drv(data)
        assert result == "DRV:P3|L26|F:42.3L/3.2(13L)|TYR:72/68/65/63·92/94/98/96"

    def test_drv_omits_tyr_on_lap_3(self):
        """TYR debe omitirse cuando lap <= 3."""
        data = {
            "lap": 3,
            "position": 5,
            "fuel": 91.2,
            "fuel_rate_trend": 0.0,
            "laps_rest": 30,
            "tyre_wear": [10, 10, 10, 10],
            "tyre_temps": [80, 80, 80, 80],
        }
        result = _format_drv(data)
        assert "TYR:" not in result
        assert "DRV:P5|L3" in result

    def test_drv_omits_tyr_on_lap_1(self):
        """TYR debe omitirse en lap 1."""
        data = {
            "lap": 1,
            "position": 1,
            "fuel": 100.0,
            "fuel_rate_trend": 0.0,
            "laps_rest": 0,
            "tyre_wear": [0, 0, 0, 0],
            "tyre_temps": [60, 60, 60, 60],
        }
        result = _format_drv(data)
        assert "TYR:" not in result


class TestFormatBRK:
    """Tests para la línea BRK."""

    def test_brk_with_values(self):
        """BRK con desgaste de frenos normal."""
        data = {"brake_wear": [38, 35, 22, 20]}
        result = _format_brk(data)
        assert result == "BRK:38/35/22/20"

    def test_brk_all_zero(self):
        """BRK debe ser línea vacía si todos los valores son 0."""
        data = {"brake_wear": [0, 0, 0, 0]}
        result = _format_brk(data)
        assert result == ""


class TestFormatGAP:
    """Tests para la línea GAP."""

    def test_gap_full(self):
        """GAP con ambos rivales adelante y detrás."""
        data = {
            "ahead_name": "VST",
            "ahead_gap": 2.1,
            "ahead_best": 108.2,
            "behind_name": "ALO",
            "behind_gap": 1.2,
            "behind_best": 107.9,
            "delta": -0.3,
        }
        result = _format_gap(data)
        # 108.2 segundos = 1:48.2 (1 min + 48.2 seg)
        # 107.9 segundos = 1:47.9
        assert result == "GAP>VST:+2.1·1:48.2|<ALO:-1.2·1:47.9·d-0.3"

    def test_gap_no_ahead(self):
        """GAP sin rival adelante (líder)."""
        data = {
            "ahead_name": None,
            "ahead_gap": None,
            "ahead_best": None,
            "behind_name": "ALO",
            "behind_gap": 1.5,
            "behind_best": 107.5,
            "delta": 0.5,
        }
        result = _format_gap(data)
        assert result.startswith("GAP<")
        assert ">:" not in result

    def test_gap_no_behind(self):
        """GAP sin rival detrás (último)."""
        data = {
            "ahead_name": "VST",
            "ahead_gap": 2.1,
            "ahead_best": 108.2,
            "behind_name": None,
            "behind_gap": None,
            "behind_best": None,
            "delta": -0.5,
        }
        result = _format_gap(data)
        assert result.startswith("GAP>")
        assert "<" not in result or ":<" not in result


class TestFormatSES:
    """Tests para la línea SES."""

    def test_ses_race_short_time(self):
        """SES con tiempo < 1 hora."""
        data = {
            "class": "Hypercar",
            "type": "RACE",
            "total_laps": 38,
            "time_left": 2722,  # 45:22
        }
        result = _format_ses(data)
        assert result == "SES:HY|RACE|38L|45:22"

    def test_ses_race_long_time(self):
        """SES con tiempo >= 1 hora."""
        data = {
            "class": "Hypercar",
            "type": "RACE",
            "total_laps": 38,
            "time_left": 7322,  # 2:02:02
        }
        result = _format_ses(data)
        assert result == "SES:HY|RACE|38L|2:02:02"

    def test_ses_gt3_class(self):
        """SES con clase GT3."""
        data = {
            "class": "GT3",
            "type": "QUALI",
            "total_laps": 0,
            "time_left": 900,  # 15:00
        }
        result = _format_ses(data)
        assert "GT3" in result
        assert "QUALI" in result

    def test_ses_practice(self):
        """SES con sesión practice."""
        data = {
            "class": "LMP2",
            "type": "practice",
            "total_laps": 0,
            "time_left": 1800,  # 30:00
        }
        result = _format_ses(data)
        assert "PRACTICE" in result


class TestFormatWTH:
    """Tests para la línea WTH."""

    def test_wth_no_sc(self):
        """WTH sin Safety Car."""
        data = {
            "grip": 2,
            "ambient_temp": 22,
            "rain_chance": 30,
            "rain_min": 15,
            "safety_car_active": False,
        }
        result = _format_wth(data)
        assert result == "WTH:MED|22°|30%+15m|SC:N"

    def test_wth_with_sc(self):
        """WTH con Safety Car activo."""
        data = {
            "grip": 2,
            "ambient_temp": 22,
            "rain_chance": 30,
            "rain_min": 15,
            "safety_car_active": True,
        }
        result = _format_wth(data)
        assert result == "WTH:MED|22°|30%+15m|SC:S"

    def test_wth_grip_mappings(self):
        """Verifica mapeo correcto de grip levels."""
        grip_values = {0: "GRN", 1: "LOW", 2: "MED", 3: "HIG", 4: "SAT"}
        for grip_val, expected in grip_values.items():
            data = {
                "grip": grip_val,
                "ambient_temp": 20,
                "rain_chance": 0,
                "rain_min": 0,
                "safety_car_active": False,
            }
            result = _format_wth(data)
            assert expected in result, f"Grip {grip_val} should map to {expected}"


class TestFormatRIV:
    """Tests para la línea RIV."""

    def test_riv_with_competitors(self):
        """RIV con competidores en diferentes categorías."""
        data = {
            "total_cars": 85,
            "competitors": [
                {"name": "VST", "class": "HY", "gap": 2.1, "laps": 22, "laps_behind": 0},
                {"name": "ALO", "class": "HY", "gap": 1.2, "laps": 22, "laps_behind": 0},
                {"name": "BOR", "class": "GT3", "gap": 12.3, "laps": 21, "laps_behind": 0},
                {"name": "AND", "class": "GT3", "gap": 31.5, "laps": 20, "laps_behind": 0},
                {"name": "VAN", "class": "GT3", "laps": 21, "laps_behind": 1},
            ],
        }
        result = _format_riv(data)
        assert "RIV:85 cars" in result
        assert "CLS1(2):" in result  # VST, ALO (gap < 5s)
        assert "CLS2(1):" in result  # BOR (gap 5-30s)
        assert "FAR(1):" in result    # AND (gap > 30s)
        assert "LAP(1):" in result   # VAN (laps_behind >= 1)

    def test_riv_empty_competitors(self):
        """RIV sin competidores."""
        data = {
            "total_cars": 1,
            "competitors": [],
        }
        result = _format_riv(data)
        assert "RIV:1 cars" in result
        assert "CLS1(0):" in result or "CLS1(0)" in result


class TestFormatTime:
    """Tests para _format_time()."""

    def test_time_short(self):
        """Tiempo < 1 hora: MM:SS"""
        assert _format_time(2722) == "45:22"

    def test_time_long(self):
        """Tiempo >= 1 hora: H:MM:SS"""
        assert _format_time(7322) == "2:02:02"

    def test_time_exact_minute(self):
        """Tiempo en minuto exacto."""
        assert _format_time(120) == "2:00"

    def test_time_zero(self):
        """Tiempo cero."""
        assert _format_time(0) == "0:00"


class TestFormatLaptime:
    """Tests para _format_laptime()."""

    def test_laptime_normal(self):
        """Tiempo de vuelta normal (ej: 108.2s = 1:48.2)."""
        assert _format_laptime(108.2) == "1:48.2"

    def test_laptime_short(self):
        """Tiempo de vuelta corto."""
        assert _format_laptime(90.5) == "1:30.5"

    def test_laptime_under_minute(self):
        """Tiempo de vuelta < 1 minuto."""
        assert _format_laptime(45.3) == "0:45.3"


class TestGenerateTicker:
    """Tests de integración para generate_ticker()."""

    def test_complete_ticker(self):
        """Ticker completo con todas las secciones."""
        data = {
            # DRV
            "lap": 26,
            "position": 3,
            "fuel": 42.3,
            "fuel_rate_trend": 3.2,
            "laps_rest": 13,
            "tyre_wear": [72, 68, 65, 63],
            "tyre_temps": [92, 94, 98, 96],
            # BRK
            "brake_wear": [38, 35, 22, 20],
            # GAP
            "ahead_name": "VST",
            "ahead_gap": 2.1,
            "ahead_best": 108.2,
            "behind_name": "ALO",
            "behind_gap": 1.2,
            "behind_best": 107.9,
            "delta": -0.3,
            # SES
            "session_class": "Hypercar",
            "session_type": "RACE",
            "total_laps": 38,
            "time_left": 2722,
            # WTH
            "grip": 2,
            "ambient_temp": 22,
            "rain_chance": 30,
            "rain_min": 15,
            "safety_car_active": False,
            # RIV
            "total_cars": 85,
            "competitors": [
                {"name": "VST", "class": "HY", "gap": 2.1, "laps": 22, "laps_behind": 0},
                {"name": "ALO", "class": "HY", "gap": 1.2, "laps": 22, "laps_behind": 0},
                {"name": "BOR", "class": "GT3", "gap": 12.3, "laps": 21, "laps_behind": 0},
            ],
        }
        result = generate_ticker(data)

        # Verificar todas las secciones
        assert "DRV:P3|L26|F:42.3L/3.2(13L)|TYR:72/68/65/63·92/94/98/96" in result
        assert "BRK:38/35/22/20" in result
        assert "GAP>" in result and "<" in result
        assert "SES:HY|RACE|38L|45:22" in result
        assert "WTH:MED|22°|30%+15m|SC:N" in result
        assert "RIV:85 cars" in result

    def test_ticker_minimal(self):
        """Ticker mínimo con campos requeridos."""
        data = {
            "lap": 1,
            "position": 1,
            "fuel": 100.0,
            "fuel_rate_trend": 0.0,
            "laps_rest": 0,
            "session_class": "GT3",
            "session_type": "RACE",
            "total_laps": 0,
            "time_left": 3600,
            "grip": 0,
            "ambient_temp": 20,
            "total_cars": 1,
            "competitors": [],
        }
        result = generate_ticker(data)

        # Debe tener al menos DRV y SES
        assert "DRV:P1|L1" in result
        assert "SES:GT3" in result
        # TYR debe estar omitido en lap 1
        assert "TYR:" not in result
        # BRK debe estar vacío (todos ceros)
        assert "BRK:" not in result or result.count("BRK") == 0
