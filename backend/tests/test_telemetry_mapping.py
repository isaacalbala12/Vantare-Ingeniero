import pytest
from unittest.mock import MagicMock
import time

from shared_telemetry import RaceState, VehicleData, SessionData, TyreData, BrakeData, EngineData, DriverInputs
from src.services.strategy_service import StrategyService


@pytest.fixture
def mock_reader():
    """Crea un mock de TelemetryReader que devuelve un estado simulado."""
    reader = MagicMock()
    reader.offline = True
    reader.shmm = None
    
    # 1. Construir datos de entrada
    session = SessionData(
        session_type=1,  # Practice
        time_remaining=3600.0,
        track_temp=25.0,
        ambient_temp=20.0,
        wetness_average=0.0,
        raininess=0.0,
        track_name="Spa"
    )
    
    player = VehicleData(
        slot_id=1,
        driver_name="Piloto Test",
        vehicle_name="Ferrari 499P",
        class_name="Hypercar",
        place=3,
        in_pits=False,
        lap_distance=2400.0,
        track_progress=0.34,
        current_lap=5,
        last_laptime=115.5,
        best_laptime=114.2,
        position_xyz=(100.0, 0.0, 50.0)
    )
    
    tyres = TyreData(
        compound_name=["Soft", "Soft", "Soft", "Soft"],
        wear=[0.1, 0.12, 0.08, 0.09],  # Desgaste (0.0 a 1.0, donde 1.0 es 100% gastado)
        pressures=[200.0, 201.0, 202.0, 203.0],
        temperatures_ico=[(80.0, 81.0, 82.0)] * 4,
        carcass_temperatures=[81.0, 82.0, 83.0, 84.0]
    )
    
    brakes = BrakeData(
        temperatures=[300.0, 305.0, 290.0, 295.0],
        wear_thickness=[0.02, 0.02, 0.02, 0.02],
        bias_front=0.54
    )
    
    engine = EngineData(
        gear=3,
        rpm=8000.0,
        max_rpm=9500.0,
        water_temp=85.0,
        oil_temp=95.0,
        lift_and_coast_progress=0.0
    )
    
    inputs = DriverInputs(
        throttle=0.85,
        brake=0.0,
        clutch=0.0,
        steering=0.05
    )
    
    race_state = RaceState(
        session=session,
        player=player,
        tyres=tyres,
        brakes=brakes,
        engine=engine,
        inputs=inputs,
        opponents={},
        timestamp=time.monotonic()
    )
    
    reader.get_state.return_value = race_state
    return reader


def test_strategy_service_mapping(mock_reader):
    """Verifica que el StrategyService procese y mapee la telemetría a frames correctamente."""
    service = StrategyService(mock_reader)
    
    # Ejecutar un ciclo de procesamiento manual
    service._process_cycle()
    
    # Comprobar que se calculó el consejo estratégico
    advice = service.get_latest_advice()
    assert advice is not None
    
    # Comprobar que los campos clave fueron mapeados y escalados correctamente
    # En offline, wear va de 1.0 (nuevo) a 0.0 (gastado)
    # mock_reader wear = 0.1, en offline se convierte a (1.0 - 0.1) * 100 = 90%
    assert advice.tyres.wear_fl == pytest.approx(90.0)
    assert service.state.tyres.tread_last[0] == pytest.approx(90.0)
    assert service.latest_frame.lap_number == 5
    
    # Verificar la generación del resumen para el LLM
    summary = service.get_race_summary()
    assert summary["session_type"] == "practice"
    assert summary["lap_number"] == 5
    assert summary["position"] == 3
    assert summary["tyres"]["wear_fl"] == 90.0
    assert summary["tyres"]["temp_fl"] == 81.0
