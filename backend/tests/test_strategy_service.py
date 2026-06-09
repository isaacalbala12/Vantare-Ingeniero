"""Tests para StrategyService."""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock


class TestStrategyService:
    """Tests del servicio de estrategia."""

    @pytest.fixture
    def service(self):
        """Crea un StrategyService con reader mockeado."""
        from src.services.strategy_service import StrategyService
        mock_reader = MagicMock()
        mock_state = MagicMock()
        mock_state.player = None
        mock_reader.get_state.return_value = mock_state
        mock_reader.offline = True
        return StrategyService(reader=mock_reader)

    def test_initialization(self, service):
        """StrategyService se inicializa correctamente."""
        assert service is not None
        assert service._loop_task is None
        assert service.latest_advice is None
        assert service.latest_frame is None

    def test_get_latest_advice_no_data(self, service):
        """get_latest_advice sin datos debe devolver None."""
        result = service.get_latest_advice()
        assert result is None

    def test_get_latest_advice_with_data(self, service):
        """get_latest_advice con datos debe devolver el consejo."""
        from shared_strategy import StrategyAdvice
        mock_advice = MagicMock(spec=StrategyAdvice)
        service.latest_advice = mock_advice
        result = service.get_latest_advice()
        assert result is mock_advice

    @patch('asyncio.create_task')
    def test_start(self, mock_create_task):
        """start debe crear una tarea asíncrona."""
        from src.services.strategy_service import StrategyService
        mock_reader = MagicMock()
        mock_reader.offline = True
        mock_reader.get_state.return_value = MagicMock(player=None)

        mock_task = MagicMock()
        mock_create_task.return_value = mock_task

        service = StrategyService(reader=mock_reader)
        service.start()

        assert service._loop_task is mock_task
        mock_create_task.assert_called_once()

    @patch('asyncio.create_task')
    def test_start_idempotent(self, mock_create_task):
        """Llamar start dos veces no debe crear múltiples tareas."""
        from src.services.strategy_service import StrategyService
        mock_reader = MagicMock()
        mock_reader.offline = True
        mock_reader.get_state.return_value = MagicMock(player=None)

        mock_task = MagicMock()
        mock_create_task.return_value = mock_task

        service = StrategyService(reader=mock_reader)
        service.start()
        first_task = service._loop_task
        service.start()
        assert service._loop_task is first_task
        # Solo debe llamarse una vez
        assert mock_create_task.call_count == 1

    @pytest.mark.asyncio
    async def test_stop(self, service):
        """stop debe cancelar la tarea y limpiar _loop_task."""
        # Crear una tarea mock
        mock_task = asyncio.create_task(asyncio.sleep(10))
        service._loop_task = mock_task

        await service.stop()
        assert service._loop_task is None
        # Verificar que la tarea fue cancelada
        assert mock_task.cancelled()

    def test_get_race_summary_no_player(self, service):
        """get_race_summary sin player debe devolver estado inactivo."""
        mock_state = MagicMock()
        mock_state.player = None
        service.reader.get_state.return_value = mock_state

        summary = service.get_race_summary()
        assert isinstance(summary, dict)
        assert summary.get("status") == "No en pista o telemetría inactiva"

    def test_get_race_summary_with_player(self, service):
        """get_race_summary con player debe devolver resumen de carrera."""
        from shared_telemetry import RaceState, VehicleData, SessionData, TyreData, BrakeData, EngineData, DriverInputs

        # Crear estado con player
        session = SessionData(
            session_type=10, time_remaining=3600.0,
            track_temp=25.0, ambient_temp=20.0, wetness_average=0.0,
            raininess=0.0, track_name="Spa",
        )
        player = VehicleData(
            slot_id=1, driver_name="Test", vehicle_name="LMH",
            class_name="LMH", place=5, in_pits=False, lap_distance=1200.0,
            track_progress=0.17, current_lap=3, last_laptime=115.5,
            best_laptime=114.2, position_xyz=(100.0, 0.0, 50.0),
        )
        tyres = TyreData(
            compound_name=["Soft", "Soft", "Soft", "Soft"],
            wear=[0.1, 0.12, 0.08, 0.09],
            pressures=[200.0, 201.0, 202.0, 203.0],
            temperatures_ico=[(80.0, 81.0, 82.0)] * 4,
            carcass_temperatures=[81.0, 82.0, 83.0, 84.0],
        )
        brakes = BrakeData(
            temperatures=[300.0, 305.0, 290.0, 295.0],
            wear_thickness=[0.02, 0.02, 0.02, 0.02],
            bias_front=0.54,
        )
        engine = EngineData(
            gear=3, rpm=8000.0, max_rpm=9500.0,
            water_temp=85.0, oil_temp=95.0, lift_and_coast_progress=0.0,
        )
        inputs = DriverInputs(throttle=0.85, brake=0.0, clutch=0.0, steering=0.05)

        race_state = RaceState(
            session=session, player=player, tyres=tyres,
            brakes=brakes, engine=engine, inputs=inputs,
            opponents={}, timestamp=0.0,
        )
        service.reader.get_state.return_value = race_state
        service.reader.offline = True

        summary = service.get_race_summary()
        assert isinstance(summary, dict)
        assert summary.get("session_type") == "race"
        assert summary.get("lap_number") == 3
        assert summary.get("position") == 5
        assert "tyres" in summary
        assert "wear_fl" in summary["tyres"]

    def test_get_race_summary_session_types(self, service):
        """get_race_summary debe clasificar correctamente los tipos de sesión."""
        from shared_telemetry import RaceState, VehicleData, SessionData, TyreData, BrakeData, EngineData, DriverInputs

        session = SessionData(
            session_type=0, time_remaining=3600.0,
            track_temp=25.0, ambient_temp=20.0, wetness_average=0.0,
            raininess=0.0, track_name="Spa",
        )
        player = VehicleData(
            slot_id=1, driver_name="Test", vehicle_name="LMH",
            class_name="LMH", place=5, in_pits=False, lap_distance=1200.0,
            track_progress=0.17, current_lap=3, last_laptime=115.5,
            best_laptime=114.2, position_xyz=(100.0, 0.0, 50.0),
        )
        tyres = TyreData(
            compound_name=["Soft", "Soft", "Soft", "Soft"],
            wear=[0.1, 0.12, 0.08, 0.09],
            pressures=[200.0, 201.0, 202.0, 203.0],
            temperatures_ico=[(80.0, 81.0, 82.0)] * 4,
            carcass_temperatures=[81.0, 82.0, 83.0, 84.0],
        )
        brakes = BrakeData(
            temperatures=[300.0, 305.0, 290.0, 295.0],
            wear_thickness=[0.02, 0.02, 0.02, 0.02],
            bias_front=0.54,
        )
        engine = EngineData(
            gear=3, rpm=8000.0, max_rpm=9500.0,
            water_temp=85.0, oil_temp=95.0, lift_and_coast_progress=0.0,
        )
        inputs = DriverInputs(throttle=0.85, brake=0.0, clutch=0.0, steering=0.05)

        race_state = RaceState(
            session=session, player=player, tyres=tyres,
            brakes=brakes, engine=engine, inputs=inputs,
            opponents={}, timestamp=0.0,
        )
        service.reader.get_state.return_value = race_state

        summary = service.get_race_summary()
        assert summary.get("session_type") == "practice"

        session_race = SessionData(
            session_type=10, time_remaining=3600.0,
            track_temp=25.0, ambient_temp=20.0, wetness_average=0.0,
            raininess=0.0, track_name="Spa",
        )
        race_state.session = session_race
        summary_race = service.get_race_summary()
        assert summary_race.get("session_type") == "race"


class TestStrategyHelpers:
    """Tests de funciones helper."""

    def test_safe_float_with_number(self):
        """safe_float con número debe devolver el número."""
        from src.services.strategy_service import safe_float
        assert safe_float(42.5) == 42.5

    def test_safe_float_with_none(self):
        """safe_float con None debe devolver 0.0."""
        from src.services.strategy_service import safe_float
        assert safe_float(None) == 0.0

    def test_safe_float_with_string(self):
        """safe_float con string numérico debe convertirlo."""
        from src.services.strategy_service import safe_float
        assert safe_float("42.5") == 42.5

    def test_safe_float_with_invalid_string(self):
        """safe_float con string inválido debe devolver 0.0."""
        from src.services.strategy_service import safe_float
        assert safe_float("not a number") == 0.0

    def test_safe_float_with_inf(self):
        """safe_float con inf debe devolver 0.0."""
        from src.services.strategy_service import safe_float
        import math
        assert safe_float(math.inf) == 0.0

    def test_safe_float_with_nan(self):
        """safe_float con nan debe devolver 0.0."""
        from src.services.strategy_service import safe_float
        import math
        assert safe_float(math.nan) == 0.0

    def test_safe_str_with_string(self):
        """safe_str con string debe devolver el string."""
        from src.services.strategy_service import safe_str
        assert safe_str("test") == "test"

    def test_safe_str_with_none(self):
        """safe_str con None debe devolver string vacío."""
        from src.services.strategy_service import safe_str
        assert safe_str(None) == ""

    def test_safe_str_with_number(self):
        """safe_str con número debe convertirlo a string."""
        from src.services.strategy_service import safe_str
        assert safe_str(42) == "42"

    def test_safe_str_with_bytes(self):
        """safe_str con bytes debe decodificarlos correctamente."""
        from src.services.strategy_service import safe_str
        result = safe_str(b"test\x00\x00")
        assert result == "test"

    def test_safe_str_with_empty_bytes(self):
        """safe_str con bytes vacíos debe devolver string vacío."""
        from src.services.strategy_service import safe_str
        assert safe_str(b"") == ""

    def test_safe_str_with_unicode_bytes(self):
        """safe_str con bytes unicode debe manejar caracteres especiales."""
        from src.services.strategy_service import safe_str
        result = safe_str("café".encode("utf-8"))
        assert result == "café"


class TestStrategyServiceState:
    """Tests del estado interno del StrategyService."""

    @pytest.fixture
    def service(self):
        from src.services.strategy_service import StrategyService
        mock_reader = MagicMock()
        mock_state = MagicMock()
        mock_state.player = None
        mock_reader.get_state.return_value = mock_state
        mock_reader.offline = True
        return StrategyService(reader=mock_reader)

    def test_initial_state(self, service):
        """Estado inicial debe tener valores por defecto."""
        assert service.state is not None
        assert service.track is not None
        assert service.track.track_length == 7004.0

    def test_lap_accumulators_initialized(self, service):
        """Acumuladores de vuelta deben estar inicializados."""
        assert service._frame_state.simulated_fuel == 100.0
        assert service._frame_state.last_lap == 0
        assert service._frame_state.lap_fuel_start == 100.0
        assert service._frame_state.prev_battery_charge == 100.0
        assert service._frame_state.lap_battery_drain == 0.0
        assert service._frame_state.lap_battery_regen == 0.0
