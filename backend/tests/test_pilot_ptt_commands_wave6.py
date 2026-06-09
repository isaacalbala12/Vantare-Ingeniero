import pytest
from unittest.mock import MagicMock

from src.intelligence import prompt_templates
from src.intelligence.pilot_tool_executor import PilotToolExecutor
from src.intelligence.triggers import DriverSwapTrigger
from src.intelligence.proactive_monitors import ProactiveMonitorSuite


@pytest.mark.asyncio
async def test_get_flag_status_tool():
    eng = MagicMock()
    eng._resolve_ptt_telemetry.return_value = {"yellow_flag_state": 2, "safety_car_active": False}
    eng._eval_session = {}
    result = await PilotToolExecutor().run(eng, "get_flag_status", {})
    assert result.ok is True
    assert result.spoken_message


@pytest.mark.asyncio
async def test_watch_snip_tool_sets_session_flag():
    eng = MagicMock()
    eng._eval_session = {}
    result = await PilotToolExecutor().run(eng, "watch_snip", {"action": "snip"}, emit_voice=False)
    assert result.ok is True
    assert eng._eval_session.get("watch_snip_requested") is True


def test_wave6_tool_catalog_minimum_size():
    names = {t["function"]["name"] for t in prompt_templates.get_pilot_ptt_tools(True)}
    required = {
        "set_speak_only",
        "spotter_toggle",
        "get_fuel_status",
        "get_gap_status",
        "get_damage_report",
        "get_tire_wear",
        "set_pit_fuel",
        "monitor_competitor",
        "get_flag_status",
        "get_race_time_remaining",
        "get_pit_window_status",
        "watch_snip",
        "set_pit_tyres",
    }
    assert required.issubset(names)
    assert len(names) >= 14


def test_driver_swap_trigger_suppressed_when_cc_module_on():
    t = DriverSwapTrigger()
    tele = {"driver_name": "Bob", "session_type": "RACE"}
    session = {"enable_driver_swap_messages": True}
    t._last_driver = "Alice"
    assert t.condition(tele, {}, session) is False


def test_proactive_no_driver_swap_after_cutover():
    suite = ProactiveMonitorSuite()
    events = suite.evaluate(
        {"driver_swap_active": True, "session_type": "RACE", "lap_number": 5},
        {},
        {"phase": "RACE"},
    )
    assert not any(e[0] == "driver_swaps" for e in events)
