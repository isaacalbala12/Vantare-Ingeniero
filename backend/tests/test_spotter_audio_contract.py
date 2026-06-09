"""Contrato audio del spotter: categorías, prioridades y elegibilidad de voz."""

from __future__ import annotations

import pytest

from src.intelligence.spotter import SpotterService
from tests.fixtures.audio_trigger_matrix import SPOTTER_AUDIO_ROWS


def _voice_eligible(audio_priority: str) -> bool:
    try:
        return int(audio_priority) >= 2
    except ValueError:
        return False


@pytest.mark.parametrize("row", [r for r in SPOTTER_AUDIO_ROWS if r.ws_event == "alert"], ids=lambda r: r.id)
def test_spotter_matrix_voice_rules(row):
    eligible = _voice_eligible(row.audio_priority)
    assert eligible == row.expect_voice


def test_spotter_proximity_alert_priority_from_service():
    from tests.test_spotter_proximity_pipeline import make_side_by_side_race_frame
    from src.intelligence.spotter_adapter import frame_to_spotter_tick

    captured: list = []

    def capture(msg):
        captured.append(msg)

    spotter = SpotterService(broadcast_callback=capture, invert_lateral=False, enabled=True)
    tick = frame_to_spotter_tick(make_side_by_side_race_frame(), advice=None)
    spotter.evaluate_tick(tick)

    prox = [m for m in captured if getattr(m, "category", None) == "proximity"]
    assert prox, "debe emitir alerta proximity"
    assert int(prox[0].audio_priority) >= 2


def test_spotter_gaps_priority_one_no_voice():
    """Gaps usan priority 1 — solo UI en frontend."""
    row = next(r for r in SPOTTER_AUDIO_ROWS if r.id == "spotter:gaps")
    assert row.audio_priority == "1"
    assert row.expect_voice is False
