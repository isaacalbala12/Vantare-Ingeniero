"""Tests para VerbosityEngine."""

import time

from src.intelligence.verbosity import VerbosityEngine, VerbosityLevel


def test_full_verbosity_when_open_track():
    engine = VerbosityEngine()
    assert engine.evaluate({"speed": 50, "gap_ahead": 10, "gap_behind": 10}) == VerbosityLevel.FULL


def test_low_verbosity_in_close_traffic():
    engine = VerbosityEngine()
    assert engine.evaluate({"speed": 50, "gap_ahead": 1.0, "gap_behind": 1.0}) == VerbosityLevel.LOW


def test_med_verbosity_in_traffic():
    engine = VerbosityEngine()
    assert engine.evaluate({"speed": 50, "gap_ahead": 2.5, "gap_behind": 2.5}) == VerbosityLevel.MED


def test_low_when_car_very_close():
    engine = VerbosityEngine()
    assert engine.evaluate({"speed": 50, "gap_ahead": 0.8, "gap_behind": 99}) == VerbosityLevel.LOW


def test_caches_for_1_second():
    engine = VerbosityEngine()
    engine._next_update = time.monotonic() + 10
    assert engine.evaluate({"speed": 50, "gap_ahead": 1.0, "gap_behind": 1.0}) == VerbosityLevel.FULL


def test_full_when_speed_below_threshold():
    engine = VerbosityEngine()
    assert engine.evaluate({"speed": 3, "gap_ahead": 0.5, "gap_behind": 0.5}) == VerbosityLevel.FULL
