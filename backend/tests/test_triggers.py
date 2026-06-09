"""
Tests unitarios para el sistema de triggers de la capa de inteligencia.

Verifica:
- Cada trigger tiene prioridad, cooldown y tier definidos.
- Condiciones de disparo correctas (FuelCritical, SafetyCar, etc.).
- Cooldown funciona (should_evaluate retorna False si se llama muy seguido).
"""
import time
import pytest
from src.intelligence.triggers import (
    get_all_triggers,
    BaseTrigger,
    FuelCriticalTrigger,
    FlagsMonitorTrigger,
    SafetyCarTrigger,
    BrakeWearCriticalTrigger,
    TiresThermalOverheatingTrigger,
    TyreDegAccelTrigger,
    HybridDeployMapTrigger,
    WeatherChangeTrigger,
    PitWindowOpenedTrigger,
    PitWindowClosingTrigger,
    CompetitorPittedTrigger,
    GapClosedTrigger,
    PhaseChangedTrigger,
    PilotQuestionTrigger,
    Priority,
    ContextTier,
    TriggerAction,
)


class TestTriggerStructure:
    """Verifica la estructura básica de cada trigger."""

    def test_all_triggers_have_required_attributes(self):
        """Cada trigger debe tener priority, min_interval, tier, action y description."""
        triggers = get_all_triggers()
        assert len(triggers) == 3, "Post-cutover: Weather, Phase, PilotQuestion"

        for trigger in triggers:
            assert isinstance(trigger, BaseTrigger)
            assert isinstance(trigger.priority, Priority), f"{trigger.__class__.__name__}: priority no es Priority"
            assert isinstance(trigger.min_interval, (int, float)), f"{trigger.__class__.__name__}: min_interval no es numérico"
            assert trigger.min_interval >= 0, f"{trigger.__class__.__name__}: min_interval negativo"
            assert isinstance(trigger.tier, ContextTier), f"{trigger.__class__.__name__}: tier no es ContextTier"
            assert isinstance(trigger.action, TriggerAction), f"{trigger.__class__.__name__}: action no es TriggerAction"
            assert isinstance(trigger.description, str) and len(trigger.description) > 0, f"{trigger.__class__.__name__}: description vacía"

    def test_triggers_priority_order(self):
        """Los triggers activos post-cutover son todos HIGH."""
        triggers = get_all_triggers()
        assert all(t.priority.value == 3 for t in triggers)

    def test_pilot_question_in_active_triggers(self):
        triggers = get_all_triggers()
        names = {t.__class__.__name__ for t in triggers}
        assert "PilotQuestionTrigger" in names
        assert "WeatherChangeTrigger" in names
        assert "PhaseChangedTrigger" in names

    def test_cooldown_values_reasonable(self):
        """Los cooldowns deben estar entre 0 y 300 segundos."""
        triggers = get_all_triggers()
        for t in triggers:
            assert 0 <= t.min_interval <= 300, f"{t.__class__.__name__}: min_interval={t.min_interval} fuera de rango"


class TestFuelCriticalTrigger:
    """Combustible críticamente bajo (< 3 vueltas)."""

    @pytest.fixture
    def trigger(self):
        return FuelCriticalTrigger()

    def test_triggers_when_fuel_below_3_laps(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        strategy = dict(mock_strategy_dict)
        strategy["fuel"]["estimated_laps_remaining"] = 2.5
        strategy["fuel"]["pit_stops_needed"] = 1
        assert trigger.condition(mock_telemetry_dict, strategy, mock_session_dict) is True
        assert trigger.condition(mock_telemetry_dict, strategy, mock_session_dict) is False

    def test_triggers_at_exactly_3_laps(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        strategy = dict(mock_strategy_dict)
        strategy["fuel"]["estimated_laps_remaining"] = 3.0
        # Condición: < 3.0, 3.0 no debería disparar
        assert trigger.condition(mock_telemetry_dict, strategy, mock_session_dict) is False

    def test_not_triggers_when_fuel_above_5_laps(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        strategy = dict(mock_strategy_dict)
        strategy["fuel"]["estimated_laps_remaining"] = 5.5
        assert trigger.condition(mock_telemetry_dict, strategy, mock_session_dict) is False

    def test_not_triggers_when_in_pits(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        strategy = dict(mock_strategy_dict)
        strategy["fuel"]["estimated_laps_remaining"] = 2.0
        telemetry = dict(mock_telemetry_dict)
        telemetry["in_pits"] = True
        assert trigger.condition(telemetry, strategy, mock_session_dict) is False

    def test_not_triggers_with_unknown_fuel(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        strategy = {"fuel": {}}  # Sin estimated_laps_remaining
        assert trigger.condition(mock_telemetry_dict, strategy, mock_session_dict) is False


class TestFlagsMonitorTrigger:
    """Flags monitor — SC/FCY y transiciones de bandera."""

    @pytest.fixture
    def trigger(self):
        return FlagsMonitorTrigger()

    def test_triggers_on_safety_car(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        trigger.condition(telemetry, mock_strategy_dict, mock_session_dict)
        telemetry["safety_car_active"] = True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False

    def test_triggers_on_fcy(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        trigger.condition(telemetry, mock_strategy_dict, mock_session_dict)
        telemetry["full_course_yellow_active"] = True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False

    def test_not_triggers_when_racing(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        assert trigger.condition(mock_telemetry_dict, mock_strategy_dict, mock_session_dict) is False


class TestBrakeWearCriticalTrigger:
    """Desgaste crítico de frenos (> 80%)."""

    @pytest.fixture
    def trigger(self):
        return BrakeWearCriticalTrigger()

    def test_triggers_when_brake_wear_above_80(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["brake_wear_fl"] = 85.0
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True

    def test_not_triggers_when_brake_wear_below_80(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        assert trigger.condition(mock_telemetry_dict, mock_strategy_dict, mock_session_dict) is False


class TestTiresThermalOverheatingTrigger:
    """Temperatura excesiva de neumáticos (> 105°C)."""

    @pytest.fixture
    def trigger(self):
        return TiresThermalOverheatingTrigger()

    def test_triggers_when_temp_exceeds_105(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["tyre_temp_fl"] = 110.0
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False

    def test_not_triggers_when_temps_normal(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        assert trigger.condition(mock_telemetry_dict, mock_strategy_dict, mock_session_dict) is False


class TestTyreDegAccelTrigger:
    """Degradación acelerada de neumáticos (> 25% promedio)."""

    @pytest.fixture
    def trigger(self):
        return TyreDegAccelTrigger()

    def test_triggers_when_avg_wear_above_25(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["tyre_wear_fl"] = 30.0
        telemetry["tyre_wear_fr"] = 30.0
        telemetry["tyre_wear_rl"] = 30.0
        telemetry["tyre_wear_rr"] = 30.0  # avg = 30%
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True

    def test_not_triggers_when_avg_wear_below_25(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        assert trigger.condition(mock_telemetry_dict, mock_strategy_dict, mock_session_dict) is False

    def test_not_triggers_when_in_pits(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["tyre_wear_fl"] = 30.0
        telemetry["tyre_wear_fr"] = 30.0
        telemetry["tyre_wear_rl"] = 30.0
        telemetry["tyre_wear_rr"] = 30.0
        telemetry["in_pits"] = True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False


class TestHybridDeployMapTrigger:
    """Estado SOC híbrido crítico (< 20% + descarga neta)."""

    @pytest.fixture
    def trigger(self):
        return HybridDeployMapTrigger()

    def test_triggers_when_battery_low_and_draining(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["battery_charge"] = 15.0
        telemetry["battery_drain"] = 5.0
        telemetry["battery_regen"] = 1.0  # net trend = -4.0 < 0
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True

    def test_not_triggers_when_battery_high(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        assert trigger.condition(mock_telemetry_dict, mock_strategy_dict, mock_session_dict) is False

    def test_not_triggers_when_battery_low_but_regen(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["battery_charge"] = 15.0
        telemetry["battery_drain"] = 1.0
        telemetry["battery_regen"] = 3.0  # net trend = +2.0 > 0
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False


class TestWeatherChangeTrigger:
    """Amenaza de lluvia (probabilidad > 30% en forecast)."""

    @pytest.fixture
    def trigger(self):
        return WeatherChangeTrigger()

    def test_triggers_when_rain_chance_above_30(self, trigger, mock_telemetry_dict, mock_strategy_dict):
        session = {
            "phase": "RACE",
            "weather_forecast": [
                {"WNV_RAIN_CHANCE": 35.0},
                {"WNV_RAIN_CHANCE": 10.0},
            ],
        }
        assert trigger.condition(mock_telemetry_dict, mock_strategy_dict, session) is True

    def test_not_triggers_when_rain_below_30(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        assert trigger.condition(mock_telemetry_dict, mock_strategy_dict, mock_session_dict) is False

    def test_not_triggers_with_empty_forecast(self, trigger, mock_telemetry_dict, mock_strategy_dict):
        session = {"phase": "RACE", "weather_forecast": []}
        assert trigger.condition(mock_telemetry_dict, mock_strategy_dict, session) is False


class TestPitWindowOpenedTrigger:
    """Ventana de parada abierta."""

    @pytest.fixture
    def trigger(self):
        return PitWindowOpenedTrigger()

    def test_triggers_when_window_open(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        strategy = dict(mock_strategy_dict)
        strategy["pit_window"]["pit_window_open"] = True
        assert trigger.condition(mock_telemetry_dict, strategy, mock_session_dict) is True
        assert trigger.condition(mock_telemetry_dict, strategy, mock_session_dict) is False

    def test_not_triggers_when_window_closed(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        assert trigger.condition(mock_telemetry_dict, mock_strategy_dict, mock_session_dict) is False

    def test_not_triggers_when_in_pits(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        strategy = dict(mock_strategy_dict)
        strategy["pit_window"]["pit_window_open"] = True
        telemetry = dict(mock_telemetry_dict)
        telemetry["in_pits"] = True
        assert trigger.condition(telemetry, strategy, mock_session_dict) is False


class TestPitWindowClosingTrigger:
    """Ventana cerrándose (<= 2 vueltas restantes)."""

    @pytest.fixture
    def trigger(self):
        return PitWindowClosingTrigger()

    def test_triggers_when_window_closing(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        strategy = dict(mock_strategy_dict)
        strategy["pit_window"]["pit_window_open"] = True
        strategy["pit_window"]["optimal_pit_lap"] = 5
        telemetry = dict(mock_telemetry_dict)
        telemetry["lap_number"] = 3  # 5 - 3 = 2 <= 2
        assert trigger.condition(telemetry, strategy, mock_session_dict) is True
        assert trigger.condition(telemetry, strategy, mock_session_dict) is False

    def test_not_triggers_when_window_just_opened(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        strategy = dict(mock_strategy_dict)
        strategy["pit_window"]["pit_window_open"] = True
        strategy["pit_window"]["optimal_pit_lap"] = 10
        telemetry = dict(mock_telemetry_dict)
        telemetry["lap_number"] = 3  # 10 - 3 = 7 > 2
        assert trigger.condition(telemetry, strategy, mock_session_dict) is False

    def test_not_triggers_when_in_pits(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        strategy = dict(mock_strategy_dict)
        strategy["pit_window"]["pit_window_open"] = True
        strategy["pit_window"]["optimal_pit_lap"] = 5
        telemetry = dict(mock_telemetry_dict)
        telemetry["lap_number"] = 3
        telemetry["in_pits"] = True
        assert trigger.condition(telemetry, strategy, mock_session_dict) is False


class TestCompetitorPittedTrigger:
    """Rival adyacente entra a boxes (transición in_pits false→true)."""

    @pytest.fixture
    def trigger(self):
        return CompetitorPittedTrigger()

    def test_triggers_on_pit_entry_transition(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["standing_position"] = 5
        telemetry["competitors"] = [
            {"standing_position": 4, "in_pits": False},
        ]
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False
        telemetry["competitors"] = [
            {"standing_position": 4, "in_pits": True},
        ]
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False

    def test_no_trigger_on_cold_start_already_in_pits(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["standing_position"] = 5
        telemetry["competitors"] = [
            {"standing_position": 6, "in_pits": True},
        ]
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False

    def test_ignores_non_adjacent_competitors(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["standing_position"] = 5
        telemetry["competitors"] = [
            {"standing_position": 2, "in_pits": False},
        ]
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False
        telemetry["competitors"] = [
            {"standing_position": 2, "in_pits": True},
        ]
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False


class TestGapClosedTrigger:
    """Brecha cerrada con rival (< 1.5s)."""

    @pytest.fixture
    def trigger(self):
        return GapClosedTrigger()

    def test_triggers_when_gap_ahead_close(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["gap_ahead"] = 1.0
        telemetry["gap_behind"] = 5.0
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False
        telemetry["gap_ahead"] = 5.0
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False
        telemetry["gap_ahead"] = 1.0
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True

    def test_triggers_when_gap_behind_close(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["gap_ahead"] = 5.0
        telemetry["gap_behind"] = 0.8
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True

    def test_not_triggers_when_gaps_wide(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        assert trigger.condition(mock_telemetry_dict, mock_strategy_dict, mock_session_dict) is False

    def test_not_triggers_when_in_pits(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["gap_ahead"] = 1.0
        telemetry["in_pits"] = True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False


class TestCooldown:
    """Verifica que should_evaluate respeta el cooldown."""

    def test_should_evaluate_returns_false_within_cooldown(self):
        """Si last_triggered es reciente, should_evaluate debe retornar False."""
        trigger = FuelCriticalTrigger()
        trigger.last_triggered = time.monotonic()  # Marcado ahora
        # Debería retornar False porque el cooldown (15s) no ha pasado
        assert trigger.should_evaluate() is False

    def test_should_evaluate_returns_true_after_cooldown(self):
        """Si pasó suficiente tiempo, should_evaluate debe retornar True."""
        trigger = FuelCriticalTrigger()
        trigger.last_triggered = time.monotonic() - 30.0  # 30 segundos atrás
        assert trigger.should_evaluate() is True

    def test_should_evaluate_returns_true_when_never_triggered(self):
        """Si nunca se ha disparado (last_triggered = 0), debe evaluar."""
        trigger = FuelCriticalTrigger()
        assert trigger.last_triggered == 0.0
        assert trigger.should_evaluate() is True

    def test_mark_triggered_updates_timestamp(self):
        """mark_triggered debe actualizar last_triggered."""
        trigger = FuelCriticalTrigger()
        before = time.monotonic()
        trigger.mark_triggered()
        assert trigger.last_triggered >= before

    def test_time_jump_detected(self):
        """Si hay un salto de tiempo > 3x min_interval, se ignora."""
        trigger = FuelCriticalTrigger()  # min_interval = 15s
        trigger.last_triggered = time.monotonic() - 100.0  # 100s atrás (> 45s = 3*15)
        # Debe retornar False y resetear last_triggered
        assert trigger.should_evaluate() is False


class TestPilotQuestionTrigger:
    """Trigger de pregunta directa del piloto (manual)."""

    def test_condition_always_false(self, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        """Este trigger es manual, su condition siempre retorna False."""
        trigger = PilotQuestionTrigger()
        assert trigger.condition(mock_telemetry_dict, mock_strategy_dict, mock_session_dict) is False

    def test_priority_is_high(self):
        trigger = PilotQuestionTrigger()
        assert trigger.priority == Priority.HIGH

    def test_no_cooldown(self):
        trigger = PilotQuestionTrigger()
        assert trigger.min_interval == 0.0
