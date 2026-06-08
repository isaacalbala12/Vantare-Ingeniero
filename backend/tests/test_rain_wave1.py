"""F6 — monitor de lluvia."""

import time

from src.intelligence.rain_monitor import RainLevel, RainLevelMonitor


def test_rain_drizzle_detected():
    monitor = RainLevelMonitor()
    result = monitor.evaluate(0.05, time.monotonic())
    assert result is not None
    assert "Llovizna" in result.message


def test_rain_heavy_detected():
    monitor = RainLevelMonitor()
    monitor._last_level = RainLevel.LIGHT
    result = monitor.evaluate(0.65, time.monotonic() + 200)
    assert result is not None
    assert "Lluvia intensa" in result.message


def test_rain_no_change_no_alert():
    monitor = RainLevelMonitor()
    monitor._last_level = RainLevel.DRIZZLE
    result = monitor.evaluate(0.05, time.monotonic())
    assert result is None


def test_rain_cooldown_suppresses():
    monitor = RainLevelMonitor()
    monitor._last_level = RainLevel.NONE
    monitor._last_alert_at = time.monotonic()
    result = monitor.evaluate(0.05, time.monotonic() + 1.0)
    assert result is None
