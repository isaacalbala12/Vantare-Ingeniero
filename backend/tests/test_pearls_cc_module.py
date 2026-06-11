"""Tests CC Pearls module respects pearl_frequency."""

from src.intelligence.crewchief_events.modules.pearls import PearlsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(session_overrides=None):
    session = {
        "verbosity_level": "detailed",
        "sweary_messages": False,
        "pearl_frequency": 0.0,
    }
    if session_overrides:
        session.update(session_overrides)
    return CrewChiefFrameContext(
        previous=None,
        current={"standing_position": 5, "lap_number": 1},
        strategy={},
        session=session,
        now_monotonic=0.0,
    )


def test_pearls_module_respects_zero_frequency():
    mod = PearlsEvent()
    assert mod.evaluate(_ctx()) == []


def test_pearls_module_high_frequency_allows_pearl():
    mod = PearlsEvent()
    ctx = _ctx({"pearl_frequency": 1.0, "verbosity_level": "detailed"})
    msgs = mod.evaluate(ctx)
    assert msgs == []
