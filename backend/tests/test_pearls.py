"""Tests perlas de sabiduría."""

from src.intelligence.pearls_of_wisdom import PearlType, PearlsService


def test_fast_lap_triggers_pearl():
    svc = PearlsService()
    msg = svc.on_event(PearlType.FAST_LAP)
    assert msg is not None
    assert len(msg) > 5


def test_max_two_per_race():
    svc = PearlsService()
    assert svc.on_event(PearlType.FAST_LAP) is not None
    assert svc.on_event(PearlType.OVERTAKE) is not None
    assert svc.on_event(PearlType.STANDARD) is None


def test_sweary_toggle_changes_pool():
    svc = PearlsService()
    clean = svc.on_event(PearlType.FAST_LAP, sweary=False)
    svc.reset_race()
    sweary = svc.on_event(PearlType.FAST_LAP, sweary=True)
    assert clean != sweary
