import pytest
import asyncio
from unittest.mock import MagicMock
from shared_strategy import StrategyAdvice, TelemetryFrame
from src.intelligence.engine import IntelligenceEngine
from src.models.messages import AlertMessage, LLMPendingMessage, AdviceStartMessage, AdviceEndMessage


@pytest.mark.asyncio
async def test_llm_task_preemption():
    """Verifica que un trigger CRITICAL interrumpe y cancela (preempción) un stream LLM activo de prioridad HIGH."""
    # 1. Configurar Mock de Broadcaster para capturar mensajes enviados
    broadcast_messages = []
    def mock_broadcast(msg):
        broadcast_messages.append(msg)

    # 2. Instanciar IntelligenceEngine con el callback de mock
    engine = IntelligenceEngine(broadcast_callback=mock_broadcast)

    # 3. Crear Mocks de TelemetryFrame y StrategyAdvice para el primer trigger
    # Trigger 1: Neumáticos Calientes (HIGH priority, STD tier, llm_required)
    frame_high = MagicMock(spec=TelemetryFrame)
    frame_high.in_garage = False
    frame_high.lap_number = 5
    frame_high.tyre_temp_fl = 110.0  # >105.0 triggers TiresThermalOverheatingTrigger
    frame_high.tyre_temp_fr = 80.0
    frame_high.tyre_temp_rl = 80.0
    frame_high.tyre_temp_rr = 80.0
    frame_high.fuel_in_tank = 30.0
    frame_high.brake_wear_fl = 10.0
    frame_high.brake_wear_fr = 10.0
    frame_high.brake_wear_rl = 10.0
    frame_high.brake_wear_rr = 10.0
    frame_high.session_type = "RACE"
    frame_high.session_time_left = 1800.0
    frame_high.session_laps_left = 15.0
    frame_high.speed = 50.0
    frame_high.battery_charge = 50.0
    frame_high.in_pits = False
    frame_high.pit_limiter_active = False
    frame_high.safety_car_active = False
    frame_high.full_course_yellow_active = False
    frame_high.yellow_flag_active = False
    frame_high.competitors = []

    advice_high = MagicMock(spec=StrategyAdvice)
    advice_high.fuel = None

    # Mock del VLLMClient para simular un streaming lento
    async def mock_streaming(prompt, tier, advice_id):
        # Primer chunk
        yield {"type": "token", "content": "Análisis "}
        await asyncio.sleep(0.4)  # Esperamos 400ms para simular streaming lento
        yield {"type": "token", "content": "térmico: "}
        await asyncio.sleep(0.4)
        yield {"type": "token", "content": "reduce ritmo."}

    engine.llm_client.ask_streaming = mock_streaming

    # Resetear cooldowns iniciales
    for trigger in engine.triggers:
        trigger.last_triggered = 0.0

    # 4. Disparar el primer trigger (Tires Overheating - HIGH)
    await engine.evaluate_cycle(frame_high, advice_high)

    # Verificar que la tarea de streaming se ha iniciado y está activa
    assert engine._current_llm_task is not None
    assert not engine._current_llm_task.done()
    assert engine._active_trigger_name == "Tires Thermal Overheating"
    assert engine._active_trigger_priority == "HIGH"

    # Esperar un poco para que empiece a recibir tokens
    await asyncio.sleep(0.1)
    assert any(isinstance(m, AdviceStartMessage) for m in broadcast_messages)

    # 5. Crear e inyectar un Trigger Crítico (Safety Car Active - CRITICAL, llm_required)
    frame_critical = MagicMock(spec=TelemetryFrame)
    frame_critical.in_garage = False
    frame_critical.lap_number = 5
    frame_critical.tyre_temp_fl = 80.0
    frame_critical.tyre_temp_fr = 80.0
    frame_critical.tyre_temp_rl = 80.0
    frame_critical.tyre_temp_rr = 80.0
    frame_critical.fuel_in_tank = 30.0
    frame_critical.brake_wear_fl = 10.0
    frame_critical.brake_wear_fr = 10.0
    frame_critical.brake_wear_rl = 10.0
    frame_critical.brake_wear_rr = 10.0
    frame_critical.session_type = "RACE"
    frame_critical.session_time_left = 1800.0
    frame_critical.session_laps_left = 15.0
    frame_critical.speed = 30.0
    frame_critical.battery_charge = 50.0
    frame_critical.in_pits = False
    frame_critical.pit_limiter_active = False
    frame_critical.safety_car_active = True  # CRITICAL trigger: IncidentsSafetyCarTrigger
    frame_critical.full_course_yellow_active = False
    frame_critical.yellow_flag_active = False
    frame_critical.competitors = []

    # Resetear el cooldown del trigger de Safety Car para asegurar evaluación
    for trigger in engine.triggers:
        if trigger.name == "Safety Car Active":
            trigger.last_triggered = 0.0

    # Inyectar el frame crítico
    await engine.evaluate_cycle(frame_critical, advice_high)

    # 6. Validar que la preempción se haya ejecutado
    # La tarea anterior debió ser cancelada de inmediato y sustituida por el Safety Car
    assert engine._active_trigger_name == "Safety Car Active"
    assert engine._active_trigger_priority == "CRITICAL"

    # Verificar que el mensaje especial de interrupción de radio fue enviado
    alerts = [m for m in broadcast_messages if isinstance(m, AlertMessage)]
    assert any("interrumpida" in a.message for a in alerts)

    # Esperar a que la nueva tarea de streaming termine
    await asyncio.sleep(1.0)

    # Validar que los mensajes del stream contengan el inicio y fin correctos
    pending_msgs = [m for m in broadcast_messages if isinstance(m, LLMPendingMessage)]
    assert len(pending_msgs) >= 2  # Uno para el primer trigger, otro para el crítico
    assert pending_msgs[-1].trigger_name == "Safety Car Active"
    assert pending_msgs[-1].priority == "CRITICAL"
