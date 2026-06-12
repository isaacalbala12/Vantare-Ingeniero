from src.intelligence.number_speech import format_gap_en, format_lap_time_en, format_fuel_litres_en


def test_gap_one_second_uses_words():
    assert "one second" in format_gap_en(1.0).lower()


def test_gap_plural():
    assert "seconds" in format_gap_en(3.0).lower()


def test_gap_decimal_uses_words_not_raw_digits():
    spoken = format_gap_en(1.2)
    assert "one point two" in spoken
    assert "1.2" not in spoken


def test_gap_small_decimal():
    spoken = format_gap_en(0.5)
    assert "point five" in spoken


def test_fuel_litres_pluralization():
    assert "one litre" == format_fuel_litres_en(1)
    assert "two litres" == format_fuel_litres_en(2)


def test_fuel_litres_zero():
    assert "zero litres" == format_fuel_litres_en(0)


def test_fuel_litres_decimal():
    spoken = format_fuel_litres_en(12.5)
    assert "twelve" in spoken
    assert "point five" in spoken
    assert "litres" in spoken


def test_fuel_litres_over_ninety_nine_uses_words():
    spoken = format_fuel_litres_en(105)
    assert "one hundred five litres" == spoken
    assert "105" not in spoken


def test_lap_time_english_words():
    spoken = format_lap_time_en(92.345)
    assert "one minute" in spoken
    assert "thirty two" in spoken
    assert "point three four five" in spoken


def test_lap_time_under_minute():
    spoken = format_lap_time_en(45.0)
    assert "forty five" in spoken
    assert "point" not in spoken


def test_lap_time_negative():
    assert "zero" == format_lap_time_en(-5)
