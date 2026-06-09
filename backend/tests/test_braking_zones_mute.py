"""Tests braking_zones_mute en VerbosityController."""

from src.intelligence.verbosity_controller import VerbosityController


def test_should_mute_for_braking():
    vc = VerbosityController()
    vc.set_braking_zones_mute(True)
    assert vc.should_mute_for_braking(0.2) is True
    assert vc.should_mute_for_braking(0.05) is False
    assert vc.should_mute_for_braking(None) is False


def test_braking_mute_disabled_by_default():
    vc = VerbosityController()
    assert vc.should_mute_for_braking(0.9) is False
