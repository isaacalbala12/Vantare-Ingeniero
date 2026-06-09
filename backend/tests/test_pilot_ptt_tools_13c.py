"""Tests Task 13C — catálogo PTT ampliado."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.intelligence.engine import IntelligenceEngine
from src.intelligence.llm_client import AskWithToolsResult, ParsedToolCall
from src.intelligence.pilot_tool_executor import PilotToolExecutor
from src.models.messages import AlertMessage


def _engine():
    sent = []
    llm = MagicMock()
    eng = IntelligenceEngine(broadcast_callback=sent.append, llm_client=llm)
    return eng, sent, llm


@pytest.mark.asyncio
async def test_get_damage_report_tool():
    eng, sent, _ = _engine()
    eng._eval_telemetry = {
        "damage_aero": 35.0,
        "dent_severity_max": 1,
        "tyre_flat_fl": False,
    }

    result = await PilotToolExecutor().run(eng, "get_damage_report", {})
    assert result.ok is True
    assert result.spoken_message
    assert any(isinstance(m, AlertMessage) for m in sent)


@pytest.mark.asyncio
async def test_get_tire_wear_tool():
    eng, sent, _ = _engine()
    eng._eval_telemetry = {
        "tyre_wear_fl": 72.0,
        "tyre_wear_fr": 68.0,
        "tyre_wear_rl": 55.0,
        "tyre_wear_rr": 53.0,
    }

    result = await PilotToolExecutor().run(eng, "get_tire_wear", {})
    assert result.ok is True
    assert "castigado" in (result.spoken_message or "").lower()


@pytest.mark.asyncio
async def test_set_braking_zones_mute_tool():
    eng, sent, _ = _engine()
    result = await PilotToolExecutor().run(eng, "set_braking_zones_mute", {"enabled": True})
    assert result.ok is True
    assert eng.verbosity.braking_zones_mute is True


@pytest.mark.asyncio
async def test_monitor_competitor_tool():
    eng, sent, _ = _engine()
    mock_svc = MagicMock()
    mock_svc.latest_advice = MagicMock(competitors=[])
    mock_svc.state = MagicMock(competitors=[])
    eng.strategy_service = mock_svc

    with patch("shared_strategy.competitors.start_monitoring", return_value=[]):
        result = await PilotToolExecutor().run(
            eng, "monitor_competitor", {"action": "start", "driver_index": 2}
        )
    assert result.ok is True
    assert "Monitorizando" in (result.spoken_message or "")


@pytest.mark.asyncio
async def test_set_pit_fuel_dry_run():
    eng, sent, _ = _engine()
    api = MagicMock()
    api.get_pit_menu = AsyncMock(
        return_value=[
            {
                "name": "FUEL:",
                "settings": [{"text": "10L"}, {"text": "50L"}],
                "currentSetting": 0,
            }
        ]
    )
    api.post_pit_menu = AsyncMock(return_value=True)
    eng.lmu_api = api

    result = await PilotToolExecutor().run(eng, "set_pit_fuel", {"litres": 40})
    assert result.ok is True
    assert "Simulación" in (result.spoken_message or "")
    api.post_pit_menu.assert_not_called()


@pytest.mark.asyncio
async def test_pilot_ptt_tools_catalog_includes_13c():
    from src.intelligence import prompt_templates

    names = {t["function"]["name"] for t in prompt_templates.get_pilot_ptt_tools(True)}
    assert {
        "get_damage_report",
        "get_tire_wear",
        "set_braking_zones_mute",
        "monitor_competitor",
        "set_pit_fuel",
    }.issubset(names)


@pytest.mark.asyncio
async def test_ptt_damage_via_agent():
    eng, sent, llm = _engine()
    eng._eval_telemetry = {"damage_aero": 45.0, "dent_severity_max": 1}
    llm.ask_with_tools = AsyncMock(
        return_value=AskWithToolsResult(
            tool_calls=[ParsedToolCall(name="get_damage_report", arguments={})],
        )
    )

    await eng.handle_pilot_question("¿cómo está el coche de daños?")

    voice = [m for m in sent if isinstance(m, AlertMessage) and m.category == "voice_response"]
    assert voice
