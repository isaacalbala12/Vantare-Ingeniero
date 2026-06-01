import pytest
from src.services.colloquial_time import SpanishColloquialTimeReader


@pytest.fixture
def reader():
    return SpanishColloquialTimeReader()


class TestSpanishColloquialTime:
    def test_en_punto(self, reader):
        assert "las tres en punto" in reader.to_colloquial(15, 0)
        assert "la una en punto" in reader.to_colloquial(13, 0)

    def test_y_cuarto(self, reader):
        assert "y cuarto" in reader.to_colloquial(10, 15)
        assert "la una y cuarto" in reader.to_colloquial(13, 15)

    def test_y_media(self, reader):
        assert "y media" in reader.to_colloquial(9, 30)

    def test_menos(self, reader):
        assert "menos cuarto" in reader.to_colloquial(10, 45)

    def test_medianoche(self, reader):
        assert reader.to_colloquial(0, 0) == "medianoche"

    def test_mediodia(self, reader):
        assert reader.to_colloquial(12, 0) == "mediodía"

    def test_minutos_menores_30(self, reader):
        result = reader.to_colloquial(14, 20)
        assert "dos" in result and "veinte" in result

    def test_24h_wrap(self, reader):
        result = reader.to_colloquial(0, 30)
        assert "doce" in result and "y media" in result
