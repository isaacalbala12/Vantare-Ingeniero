"""
Fixtures compartidos para los tests del backend.
Proporciona estado de telemetría simulado, un cliente de prueba FastAPI,
y utilidades comunes.
"""
import pytest
from unittest.mock import MagicMock
import time

from shared_telemetry import (
    RaceState, VehicleData, SessionData, TyreData, BrakeData,
    EngineData, DriverInputs,
)


# =========================================================================
# Fixtures de Telemetría Simulada
# =========================================================================

@pytest.fixture
def mock_race_state():
    """RaceState simulado para pruebas unitarias."""
    session = SessionData(
        session_type=4,  # Race
        time_remaining=3600.0,
        track_temp=25.0,
        ambient_temp=20.0,
        wetness_average=0.0,
        raininess=0.0,
        track_name="Spa",
    )
    player = VehicleData(
        slot_id=1,
        driver_name="Piloto Test",
        vehicle_name="Hypercar",
        class_name="LMH",
        place=5,
        in_pits=False,
        lap_distance=1200.0,
        track_progress=0.17,
        current_lap=3,
        last_laptime=115.5,
        best_laptime=114.2,
        position_xyz=(100.0, 0.0, 50.0),
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

    return RaceState(
        session=session, player=player, tyres=tyres,
        brakes=brakes, engine=engine, inputs=inputs,
        opponents={}, timestamp=time.monotonic(),
    )


@pytest.fixture
def mock_telemetry_dict():
    """Frame de telemetría como dict para evaluar triggers y spotter."""
    return {
        "lap_number": 3,
        "session_type": "RACE",
        "session_time_left": 3600.0,
        "session_laps_left": 15.0,
        "fuel_in_tank": 45.0,
        "fuel_capacity": 100.0,
        "speed": 72.0,  # m/s ~260 km/h
        "in_pits": False,
        "pit_limiter_active": False,
        "safety_car_active": False,
        "full_course_yellow_active": False,
        "yellow_flag_active": False,
        "blue_flag_active": False,
        "session_stopped": False,
        "session_over": False,
        "driver_name": "Piloto Test",
        "num_penalties": 0,
        "player_class": "Hypercar",
        "tyre_wear_fl": 10.0,
        "tyre_wear_fr": 12.0,
        "tyre_wear_rl": 8.0,
        "tyre_wear_rr": 9.0,
        "tyre_temp_fl": 85.0,
        "tyre_temp_fr": 86.0,
        "tyre_temp_rl": 84.0,
        "tyre_temp_rr": 85.0,
        "brake_wear_fl": 15.0,
        "brake_wear_fr": 15.0,
        "brake_wear_rl": 12.0,
        "brake_wear_rr": 12.0,
        "battery_charge": 60.0,
        "battery_drain": 2.0,
        "battery_regen": 1.5,
        "gap_ahead": 3.0,
        "gap_behind": 4.0,
        "standing_position": 5,
        "competitors": [],
        "damage_aero": 0.0,
        "suspension_damage": 0.0,
        "throttle": 0.85,
        "brake": 0.0,
        "engine": {"rpm": 8000, "gear": 3},
    }


@pytest.fixture
def mock_strategy_dict():
    """Estrategia como dict para evaluar triggers."""
    return {
        "fuel": {
            "fuel_in_tank": 45.0,
            "fuel_capacity": 100.0,
            "estimated_laps_remaining": 12.0,
            "fuel_needed_to_finish": 55.0,
            "fuel_rate_trend": 3.2,
        },
        "tyres": {
            "wear_fl": 10.0, "wear_fr": 12.0,
            "wear_rl": 8.0, "wear_rr": 9.0,
        },
        "pit_window": {
            "pit_window_open": False,
            "optimal_pit_lap": 10,
            "pit_loss_time": 25.0,
        },
    }


@pytest.fixture
def mock_session_dict():
    """Datos de sesión como dict para evaluar triggers climáticos."""
    return {
        "phase": "RACE",
        "finish_criteria": "TIME_LIMIT",
        "enable_fuel_messages": False,
        "enable_push_now_messages": False,
        "enable_session_end_messages": False,
        "enable_pit_stop_messages": False,
        "enable_gap_messages": False,
        "enable_fcy_messages": False,
        "enable_blue_flag_messages": False,
        "enable_multiclass_messages": False,
        "enable_driver_swap_messages": False,
        "enable_battery_messages": False,
        "enable_tyre_temp_messages": False,
        "enable_tyre_wear_messages": False,
        "enable_brake_wear_messages": False,
        "weather_forecast": [
            {"WNV_SKY": 0, "WNV_TEMPERATURE": 25.0, "WNV_RAIN_CHANCE": 5.0},
            {"WNV_SKY": 0, "WNV_TEMPERATURE": 24.5, "WNV_RAIN_CHANCE": 10.0},
        ],
    }


# =========================================================================
# Fixtures para TelemetryReader mockeado
# =========================================================================

@pytest.fixture
def mock_telemetry_reader(mock_race_state):
    """TelemetryReader simulado que devuelve un RaceState fijo."""
    reader = MagicMock()
    reader.offline = True
    reader.shmm = None
    reader.get_state.return_value = mock_race_state
    return reader


# =========================================================================
# Fixtures para Broadcast mockeado
# =========================================================================

@pytest.fixture
def broadcast_messages():
    """Lista para capturar mensajes broadcast en tests."""
    messages = []
    return messages


@pytest.fixture
def mock_broadcast(broadcast_messages):
    """Callback broadcast que acumula mensajes en una lista."""
    def _broadcast(msg):
        broadcast_messages.append(msg)
    return _broadcast
