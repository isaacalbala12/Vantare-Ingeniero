"""Contrato audio/triggers: matriz documentada + engine emite el evento WS correcto."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from src.intelligence.engine import IntelligenceEngine
from src.intelligence.triggers import (
    TriggerAction,
    get_all_triggers,
    BrakeWearCriticalTrigger,
    MulticlassWarningTrigger,
    DriverSwapTrigger,
    PenaltyMonitorTrigger,
    FuelCriticalTrigger,
    FlagsMonitorTrigger,
    PitWindowOpenedTrigger,
    PitWindowClosingTrigger,
    GapClosedTrigger,
    PushNowTrigger,
)
from src.models.messages import AlertMessage, LLMPendingMessage
from tests.fixtures.audio_trigger_matrix import (
    ALL_AUDIO_CONTRACT_ROWS,
    TRIGGER_AUDIO_ROWS,
    SPOTTER_AUDIO_ROWS,
)


def _frontend_would_voice(category: str, severity: str, audio_priority: str) -> bool:
    """Réplica mínima de alertVoice.ts para validar contrato backend→frontend."""
    no_voice = {"gaps", "system"}
    if category.lower() in no_voice:
        return False
    if severity.upper() in ("CRITICAL", "HIGH", "WARNING"):
        return True
    try:
        return int(audio_priority) >= 2
    except ValueError:
        return severity.upper() in ("CRITICAL", "HIGH", "WARNING")


class TestAudioContractMatrix:
    def test_matrix_has_all_triggers(self):
        trigger_ids = {r.id for r in TRIGGER_AUDIO_ROWS}
        for trigger in get_all_triggers():
            assert f"trigger:{trigger.__class__.__name__}" in trigger_ids

    @pytest.mark.parametrize("row", [r for r in ALL_AUDIO_CONTRACT_ROWS if r.ws_event == "alert"], ids=lambda r: r.id)
    def test_alert_voice_expectation_matches_frontend_rules(self, row):
        payload = {
            "category": row.category,
            "severity": row.severity,
            "audio_priority": row.audio_priority,
        }
        voiced = _frontend_would_voice(row.category, row.severity, row.audio_priority)
        assert voiced == row.expect_voice, (
            f"{row.id}: frontend voice={voiced} != expected {row.expect_voice}"
        )

    @pytest.mark.parametrize(
        "row",
        [r for r in ALL_AUDIO_CONTRACT_ROWS if r.ws_event == "llm_pending+advice_*"],
        ids=lambda r: r.id,
    )
    def test_advice_path_always_speaks_when_not_internal(self, row):
        """Advice LLM no pasa por shouldVoiceAlert — se vocaliza vía advice_end."""
        assert row.expect_voice is True

    @pytest.mark.parametrize(
        "row",
        [r for r in ALL_AUDIO_CONTRACT_ROWS if r.ws_event == "commentary_end"],
        ids=lambda r: r.id,
    )
    def test_commentary_end_uses_normal_tts(self, row):
        assert row.expect_voice is True
        assert row.expect_tts_priority == "NORMAL"

    @pytest.mark.parametrize("row", SPOTTER_AUDIO_ROWS, ids=lambda r: r.id)
    def test_spotter_immediate_rows_use_high_priority(self, row):
        if row.expect_tts_priority == "IMMEDIATE":
            assert row.category in (
                "proximity",
                "limiter",
                "fuel",
                "safety_car",
                "session",
                "damage",
            ) or int(row.audio_priority) >= 3


class TestTriggerActions:
    def test_no_alert_only_triggers_post_cutover(self):
        alert_only = [t for t in get_all_triggers() if t.action == TriggerAction.ALERT_ONLY]
        assert alert_only == []

    def test_llm_required_triggers_are_legacy_fallback_only(self):
        llm = [t for t in get_all_triggers() if t.action == TriggerAction.LLM_REQUIRED]
        names = {t.__class__.__name__ for t in llm}
        assert names == {
            "WeatherChangeTrigger",
            "PhaseChangedTrigger",
            "PilotQuestionTrigger",
            "FlagsMonitorTrigger",
        }


def _base_telemetry() -> dict:
    return {
        "speed": 180,
        "lap_number": 5,
        "session_type": "RACE",
        "session_time_left": 3600.0,
        "session_laps_left": 20.0,
        "in_pits": False,
        "in_garage": False,
        "brake_wear_fl": 10.0,
        "brake_wear_fr": 10.0,
        "brake_wear_rl": 10.0,
        "brake_wear_rr": 10.0,
        "tyre_temp_fl": 80.0,
        "tyre_temp_fr": 80.0,
        "tyre_temp_rl": 80.0,
        "tyre_temp_rr": 80.0,
        "tyre_wear_fl": 10.0,
        "tyre_wear_fr": 10.0,
        "tyre_wear_rl": 10.0,
        "tyre_wear_rr": 10.0,
        "battery_charge": 80.0,
        "battery_drain": 0.0,
        "battery_regen": 1.0,
        "safety_car_active": False,
        "full_course_yellow_active": False,
        "yellow_flag_active": False,
        "gap_ahead": 5.0,
        "gap_behind": 5.0,
        "standing_position": 3,
        "driver_name": "Pilot A",
        "num_penalties": 0,
        "player_class": "LMP2",
        "competitors": [],
    }


def _base_strategy() -> dict:
    return {
        "fuel": {"estimated_laps_remaining": 15.0},
        "pit_window": {"pit_window_open": False, "optimal_pit_lap": 99},
        "competitors": [],
    }


def _engine_with_capture():
    messages: list = []

    def capture(msg):
        messages.append(msg)

    engine = IntelligenceEngine(broadcast_callback=capture)
    engine._llm_warmup_until = 0.0
    for trigger in engine.triggers:
        trigger.last_triggered = 0.0
    return engine, messages


_CC_OFF_SESSION = {
    "enable_fuel_messages": False,
    "enable_brake_wear_messages": False,
    "enable_multiclass_messages": False,
    "enable_driver_swap_messages": False,
    "enable_push_now_messages": False,
    "enable_session_end_messages": False,
    "enable_pit_stop_messages": False,
    "enable_gap_messages": False,
    "enable_tyre_wear_messages": False,
    "enable_battery_messages": False,
    "enable_tyre_temp_messages": False,
}


@pytest.mark.asyncio
async def test_engine_no_legacy_brake_wear_trigger_post_cutover():
    engine, messages = _engine_with_capture()
    telemetry = _base_telemetry()
    telemetry["brake_wear_fl"] = 85.0

    await engine.evaluate_cycle(telemetry, _base_strategy(), {"phase": "RACE"})

    alerts = [m for m in messages if isinstance(m, AlertMessage)]
    assert not any("frenos" in a.message.lower() for a in alerts)


@pytest.mark.asyncio
async def test_engine_no_legacy_multiclass_trigger_post_cutover():
    engine, messages = _engine_with_capture()
    telemetry = _base_telemetry()
    telemetry["player_class"] = "LMP2"
    strategy = _base_strategy()
    strategy["competitors"] = [
        {"driver_class": "HYPERCAR", "gap_to_player": -1.2, "in_pits": False},
    ]

    await engine.evaluate_cycle(telemetry, strategy, {"phase": "RACE"})

    alerts = [m for m in messages if isinstance(m, AlertMessage)]
    assert not any("multiclase" in a.message.lower() or "HYPERCAR" in a.message for a in alerts)


@pytest.mark.asyncio
async def test_engine_no_legacy_driver_swap_trigger_post_cutover():
    engine, messages = _engine_with_capture()
    telemetry = _base_telemetry()

    await engine.evaluate_cycle(telemetry, _base_strategy(), {"phase": "RACE"})
    messages.clear()

    telemetry["driver_name"] = "Pilot B"
    await engine.evaluate_cycle(telemetry, _base_strategy(), {"phase": "RACE"})

    alerts = [m for m in messages if isinstance(m, AlertMessage)]
    assert not any("Cambio de piloto" in a.message for a in alerts)


@pytest.mark.asyncio
async def test_engine_no_legacy_penalty_trigger_post_cutover():
    engine, messages = _engine_with_capture()
    telemetry = _base_telemetry()

    await engine.evaluate_cycle(telemetry, _base_strategy(), {"phase": "RACE"})
    messages.clear()

    telemetry["num_penalties"] = 1
    await engine.evaluate_cycle(telemetry, _base_strategy(), {"phase": "RACE"})

    alerts = [m for m in messages if isinstance(m, AlertMessage)]
    assert not any("Penalización" in a.message for a in alerts)


@pytest.mark.asyncio
async def test_engine_no_legacy_fuel_critical_llm_post_cutover():
    engine, messages = _engine_with_capture()
    strategy = _base_strategy()
    strategy["fuel"] = {
        "estimated_laps_remaining": 1.5,
        "pit_stops_needed": 1,
        "fuel_needed_to_finish": 80.0,
    }

    await engine.evaluate_cycle(_base_telemetry(), strategy, {"phase": "RACE"})

    assert not any(isinstance(m, LLMPendingMessage) for m in messages)


class TestIndividualTriggerConditions:
    def test_brake_wear_condition_when_cc_gate_off(self):
        t = BrakeWearCriticalTrigger()
        session = _CC_OFF_SESSION
        assert t.condition({"brake_wear_fl": 85, "in_pits": False}, {}, session) is True
        assert t.condition({"brake_wear_fl": 50, "in_pits": False}, {}, session) is False

    def test_multiclass_condition_when_cc_gate_off(self):
        t = MulticlassWarningTrigger()
        session = _CC_OFF_SESSION
        telemetry = {"in_pits": False, "player_class": "LMP2"}
        strategy = {
            "competitors": [
                {"driver_class": "HYPERCAR", "gap_to_player": -1.0, "in_pits": False},
            ]
        }
        assert t.condition(telemetry, strategy, session) is True
        assert t.condition(telemetry, strategy, session) is False
        strategy["competitors"][0]["gap_to_player"] = -3.0
        assert t.condition(telemetry, strategy, session) is False
        strategy["competitors"][0]["gap_to_player"] = -1.0
        assert t.condition(telemetry, strategy, session) is True

    def test_brake_wear_edge_once_when_cc_gate_off(self):
        t = BrakeWearCriticalTrigger()
        session = _CC_OFF_SESSION
        tele = {"brake_wear_fl": 85, "in_pits": False}
        assert t.condition(tele, {}, session) is True
        assert t.condition(tele, {}, session) is False
        tele["brake_wear_fl"] = 70
        assert t.condition(tele, {}, session) is False
        tele["brake_wear_fl"] = 85
        assert t.condition(tele, {}, session) is True

    def test_penalty_trigger_is_stub_post_wave1(self):
        t = PenaltyMonitorTrigger()
        tele = {"num_penalties": 1}
        assert t.condition(tele, {}, _CC_OFF_SESSION) is False

    def test_fuel_critical_condition_when_cc_gate_off(self):
        t = FuelCriticalTrigger()
        session = _CC_OFF_SESSION
        strat = {"fuel": {"estimated_laps_remaining": 2.0, "pit_stops_needed": 1}}
        assert t.condition({"in_pits": False}, strat, session) is True
        assert t.condition({"in_pits": False}, strat, session) is False
        assert t.action == TriggerAction.DETERMINISTIC_ONLY

    def test_fuel_critical_suppressed_when_cc_active(self):
        t = FuelCriticalTrigger()
        strat = {"fuel": {"estimated_laps_remaining": 2.0, "pit_stops_needed": 1}}
        assert t.condition({"in_pits": False}, strat, {"enable_fuel_messages": True}) is False

    def test_llm_triggers_edge_once_when_cc_gate_off(self):
        session = _CC_OFF_SESSION
        fuel = FuelCriticalTrigger()
        pit_open = PitWindowOpenedTrigger()
        pit_close = PitWindowClosingTrigger()

        strat_fuel = {"fuel": {"estimated_laps_remaining": 2.0, "pit_stops_needed": 1}}
        assert fuel.condition({"in_pits": False}, strat_fuel, session) is True
        assert fuel.condition({"in_pits": False}, strat_fuel, session) is False
        strat_fuel["fuel"]["estimated_laps_remaining"] = 5.0
        assert fuel.condition({"in_pits": False}, strat_fuel, session) is False
        strat_fuel["fuel"]["estimated_laps_remaining"] = 2.0
        assert fuel.condition({"in_pits": False}, strat_fuel, session) is True

        strat_pit = {"pit_window": {"pit_window_open": True}}
        assert pit_open.condition({"in_pits": False}, strat_pit, session) is True
        assert pit_open.condition({"in_pits": False}, strat_pit, session) is False
        strat_pit["pit_window"]["pit_window_open"] = False
        assert pit_open.condition({"in_pits": False}, strat_pit, session) is False
        strat_pit["pit_window"]["pit_window_open"] = True
        assert pit_open.condition({"in_pits": False}, strat_pit, session) is True

        strat_close = {"pit_window": {"pit_window_open": True, "optimal_pit_lap": 5}}
        tele_lap = {"lap_number": 3, "in_pits": False}
        assert pit_close.condition(tele_lap, strat_close, session) is True
        assert pit_close.condition(tele_lap, strat_close, session) is False

        gap = GapClosedTrigger()
        tele_gap = {"gap_ahead": 1.0, "gap_behind": 5.0, "in_pits": False}
        assert gap.condition(tele_gap, {}, session) is True
        assert gap.condition(tele_gap, {}, session) is False

        push = PushNowTrigger()
        tele_push = {"session_type": "race", "session_laps_left": 2.0, "in_pits": False}
        assert push.condition(tele_push, {}, session) is True
        assert push.condition(tele_push, {}, session) is False

    def test_flags_trigger_suppressed_when_cc_owns_flags(self):
        flags = FlagsMonitorTrigger()
        tele = {"safety_car_active": False, "full_course_yellow_active": False}
        flags.condition(tele, {}, {"enable_flag_messages": True})
        tele["safety_car_active"] = True
        assert flags.condition(tele, {}, {"enable_flag_messages": True}) is False
