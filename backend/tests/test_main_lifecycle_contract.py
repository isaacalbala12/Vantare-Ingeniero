"""Contratos de arranque lifespan — evita regresiones de empaquetado."""

from pathlib import Path


def _main_source() -> str:
    return (Path(__file__).resolve().parents[1] / "src" / "main.py").read_text(encoding="utf-8")


def test_main_spawns_race_tick_not_spotter_eval_loop():
    text = _main_source()
    assert "race_tick_loop" in text
    assert "race_task = asyncio.create_task(race_tick_loop" in text
    assert "spotter_eval_loop" not in text


def test_main_uses_commentary_batch_setter_not_property_assign():
    text = _main_source()
    assert "set_enable_commentary_batch(False)" in text
    assert ".enable_commentary_batch = False" not in text
