import asyncio

import pytest
from unittest.mock import MagicMock

from shared_strategy import StrategyAdvice, TelemetryFrame
from src.intelligence.engine import IntelligenceEngine
from src.models.messages import AdviceStartMessage, AlertMessage, LLMPendingMessage


def _cc_off_session() -> dict:
    return {
        "enable_fuel_messages": False,
        "enable_fcy_messages": False,
        "enable_flag_messages": False,
        "weather_forecast": [{"WNV_RAIN_CHANCE": 50.0}],
        "phase": "RACE",
    }


@pytest.mark.asyncio
async def test_llm_task_preemption():
    """Un trigger CRITICAL interrumpe y cancela un stream LLM activo de prioridad HIGH."""
    broadcast_messages = []

    def mock_broadcast(msg):
        broadcast_messages.append(msg)

    engine = IntelligenceEngine(broadcast_callback=mock_broadcast)
    engine.engineer_enabled = True
    engine.verbosity.set_speak_only_when_spoken_to(False)
    engine._llm_warmup_until = 0.0

    async def mock_streaming(prompt, tier, advice_id, *args, **kwargs):
        yield {"type": "token", "content": "Análisis "}
        await asyncio.sleep(0.4)
        yield {"type": "token", "content": "climático: "}
        await asyncio.sleep(0.4)
        yield {"type": "token", "content": "reduce ritmo."}

    engine.llm_client.ask_streaming = mock_streaming

    for trigger in engine.triggers:
        trigger.last_triggered = 0.0

    frame_weather = MagicMock(spec=TelemetryFrame)
    frame_weather.in_garage = False
    frame_weather.lap_number = 5
    frame_weather.speed = 50.0
    frame_weather.in_pits = False
    frame_weather.session_type = "RACE"
    frame_weather.safety_car_active = False
    frame_weather.full_course_yellow_active = False
    frame_weather.yellow_flag_active = False
    frame_weather.competitors = []

    advice = MagicMock(spec=StrategyAdvice)
    advice.fuel = None

    await engine.evaluate_cycle(frame_weather, advice, _cc_off_session())

    assert engine._current_llm_task is not None
    assert not engine._current_llm_task.done()
    assert engine._active_trigger_name == "Amenaza de lluvia inminente"
    assert engine._active_trigger_priority == "HIGH"

    await asyncio.sleep(0.1)
    assert any(isinstance(m, AdviceStartMessage) for m in broadcast_messages)

    frame_critical = MagicMock(spec=TelemetryFrame)
    frame_critical.in_garage = False
    frame_critical.lap_number = 5
    frame_critical.speed = 30.0
    frame_critical.in_pits = False
    frame_critical.session_type = "RACE"
    frame_critical.safety_car_active = True
    frame_critical.full_course_yellow_active = False
    frame_critical.yellow_flag_active = False
    frame_critical.competitors = []

    for trigger in engine.triggers:
        if trigger.name == "Flags Monitor":
            trigger.last_triggered = 0.0

    await engine.evaluate_cycle(frame_critical, advice, _cc_off_session())

    assert engine._active_trigger_name == "Flags Monitor"
    assert engine._active_trigger_priority == "CRITICAL"

    alerts = [m for m in broadcast_messages if isinstance(m, AlertMessage)]
    assert any("interrumpida" in a.message for a in alerts)

    await asyncio.sleep(1.0)

    pending_msgs = [m for m in broadcast_messages if isinstance(m, LLMPendingMessage)]
    assert len(pending_msgs) >= 2
    assert pending_msgs[-1].trigger_name == "Flags Monitor"
    assert pending_msgs[-1].priority == "CRITICAL"
