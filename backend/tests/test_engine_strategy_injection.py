"""Tests de inyección explícita de StrategyService en IntelligenceEngine."""

from unittest.mock import MagicMock

from src.intelligence.engine import IntelligenceEngine


def test_get_strategy_service_returns_injected_instance():
    svc = MagicMock(name="strategy_service")
    engine = IntelligenceEngine(
        broadcaster=MagicMock(),
        llm_client=MagicMock(),
        strategy_service=svc,
    )
    assert engine._get_strategy_service() is svc


def test_get_strategy_service_without_injection_returns_none():
    engine = IntelligenceEngine(
        broadcaster=MagicMock(),
        llm_client=MagicMock(),
        strategy_service=None,
    )
    assert engine._get_strategy_service() is None


def test_get_strategy_service_does_not_use_sys_modules(monkeypatch):
    """Tras el refactor, sys.modules no debe ser el mecanismo de resolución."""
    import sys

    fake_main = MagicMock()
    fake_main.app.state.strategy_service = MagicMock(name="from_sys_modules")
    monkeypatch.setitem(sys.modules, "src.main", fake_main)

    engine = IntelligenceEngine(
        broadcaster=MagicMock(),
        llm_client=MagicMock(),
        strategy_service=None,
    )
    assert engine._get_strategy_service() is None
