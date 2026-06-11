"""Tests pearl_frequency sampling in PearlsService."""

from src.intelligence.pearls_of_wisdom import PearlType, PearlsService


def test_pearl_frequency_zero_never_emits():
    svc = PearlsService()
    for _ in range(100):
        assert svc.on_event(PearlType.STANDARD, pearl_frequency=0.0, roll=0.0) is None


def test_pearl_frequency_one_always_emits_when_under_cap():
    svc = PearlsService()
    msg = svc.on_event(PearlType.STANDARD, pearl_frequency=1.0, roll=0.0)
    assert msg


def test_pearl_frequency_half_respects_roll():
    svc = PearlsService()
    assert svc.on_event(PearlType.STANDARD, pearl_frequency=0.5, roll=0.49) is not None
    assert svc.on_event(PearlType.STANDARD, pearl_frequency=0.5, roll=0.51) is None


def test_pearl_frequency_with_sweary_pool():
    svc = PearlsService()
    svc.reset_race()
    msg = svc.on_event(PearlType.FAST_LAP, sweary=True, pearl_frequency=1.0, roll=0.0)
    assert msg
    assert any(w in msg for w in ("hostia", "infarto", "volar"))
