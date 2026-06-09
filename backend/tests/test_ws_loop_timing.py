"""Tests de utilidades de timing para bucles WebSocket."""

import time

from src.routers.websocket import TELEMETRY_INTERVAL_S, compute_loop_sleep


def test_compute_loop_sleep_returns_remaining_interval():
    start = time.monotonic()
    time.sleep(0.03)
    delay = compute_loop_sleep(TELEMETRY_INTERVAL_S, start)
    assert 0.010 <= delay <= 0.025


def test_compute_loop_sleep_never_negative():
    start = time.monotonic()
    time.sleep(0.08)
    delay = compute_loop_sleep(TELEMETRY_INTERVAL_S, start)
    assert delay == 0.0


def test_strategy_interval_constant():
    from src.routers.websocket import STRATEGY_INTERVAL_S

    assert STRATEGY_INTERVAL_S == 2.0
