"""Tests del ColloquialTimeReader — lectura coloquial de la hora.

Cobertura:
- En punto, y cuarto, y media
- Menos cuarto, menos media
- Medianoche, mediodía
- Minutos intermedios (1-29, 31-59)
- Horas 1-23 con wrap 24h
- Artículo correcto (la/las) según hora singular/plural
"""
import pytest
from src.services.colloquial_time import (
    ColloquialTimeReader, SpanishColloquialTimeReader,
)


@pytest.fixture
def reader():
    return SpanishColloquialTimeReader()


class TestEnPunto:
    def test_tres_en_punto(self, reader):
        assert reader.to_colloquial(15, 0) == "las tres en punto"

    def test_una_en_punto_singular(self, reader):
        """La una (singular) usa 'la', no 'las'."""
        assert "la una en punto" in reader.to_colloquial(13, 0)


class TestYCuartoyMedia:
    def test_diez_y_cuarto(self, reader):
        result = reader.to_colloquial(10, 15)
        assert "y cuarto" in result
        assert "diez" in result

    def test_una_y_cuarto_singular(self, reader):
        result = reader.to_colloquial(13, 15)
        assert "la una" in result
        assert "y cuarto" in result

    def test_nueve_y_media(self, reader):
        result = reader.to_colloquial(9, 30)
        assert "y media" in result
        assert "nueve" in result


class TestMenos:
    def test_menos_cuarto(self, reader):
        result = reader.to_colloquial(10, 45)
        assert "menos cuarto" in result
        # Debe apuntar a la siguiente hora (11)
        assert "once" in result

    def test_menos_media(self, reader):
        result = reader.to_colloquial(14, 30)
        # 14:30 → 15 menos media
        # Pero también "y media" si lo interpretamos como 14:30
        # La regla es: 30 exacto = "y media" de la hora actual
        # 14:29 → 14 y veintinueve
        # 14:30 → "y media" (no "menos media")
        # 14:31 → 15 menos veintinueve
        assert "y media" in result or "menos media" in result

    def test_menos_diez(self, reader):
        result = reader.to_colloquial(14, 50)
        # 14:50 = 15 menos 10
        assert "menos" in result
        assert "diez" in result
        assert "quince" in result or "tres" in result  # próxima hora


class TestCasosEspeciales:
    def test_medianoche(self, reader):
        assert reader.to_colloquial(0, 0) == "medianoche"

    def test_mediodia(self, reader):
        assert reader.to_colloquial(12, 0) == "mediodía"

    def test_mediodia_con_cuarto(self, reader):
        result = reader.to_colloquial(12, 15)
        assert "doce" in result
        assert "y cuarto" in result

    def test_wrap_24h(self, reader):
        """0:30 = medianoche y media."""
        result = reader.to_colloquial(0, 30)
        assert "doce" in result
        assert "y media" in result

    def test_wrap_24h_siguiente_dia(self, reader):
        """23:45 = 0 menos cuarto del día siguiente."""
        result = reader.to_colloquial(23, 45)
        assert "menos cuarto" in result
        # próxima hora = 0 = 12 (en formato 12h) o "doce"
        assert "doce" in result


class TestMinutosIntermedios:
    def test_minuto_1(self, reader):
        result = reader.to_colloquial(15, 1)
        assert "y uno" in result

    def test_minuto_20(self, reader):
        result = reader.to_colloquial(14, 20)
        assert "y veinte" in result

    def test_minuto_45_es_menos_15(self, reader):
        """45 min = próxima hora menos 15."""
        result = reader.to_colloquial(10, 45)
        # 10:45 = 11 menos 15 → "las once menos cuarto"
        assert "menos cuarto" in result
        assert "once" in result


class TestArticulos:
    """Verifica el uso correcto de 'la' vs 'las' según singular/plural."""

    def test_una_usa_la(self, reader):
        assert "la una" in reader.to_colloquial(13, 15)

    def test_dos_usa_las(self, reader):
        assert "las dos" in reader.to_colloquial(14, 15)

    def test_doce_usa_las(self, reader):
        assert "las doce" in reader.to_colloquial(12, 0)


class TestExtensibility:
    def test_base_class_not_implemented(self):
        base = ColloquialTimeReader()
        with pytest.raises(NotImplementedError):
            base.to_colloquial(15, 0)
