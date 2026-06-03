"""
Integration tests for SpotterService 20Hz alert path.

Tests the full evaluate_tick pipeline:
  RaceState/dict → model_dump → evaluate() → broadcast_callback

Verifica que las 6 alertas deterministas viajan correctamente
desde el estado de telemetría hasta el callback de broadcast.
"""
import time
import pytest
from src.intelligence.spotter import SpotterService
from src.models.messages import AlertMessage
from shared_telemetry import (
    RaceState, VehicleData, SessionData, TyreData, BrakeData,
    EngineData, DriverInputs,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def spotter(mock_broadcast):
    """SpotterService con broadcast_callback mockeado."""
    return SpotterService(broadcast_callback=mock_broadcast)


@pytest.fixture
def base_race_state():
    """RaceState base sin condiciones de alerta (valores nominales)."""
    session = SessionData(
        session_type=4,
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


# =========================================================================
# Helpers
# =========================================================================

def build_tick(base_state, **overrides):
    """Construye un dict plano de telemetría a partir de un RaceState + overrides.

    1. Serializa el RaceState con model_dump (incluye player.in_pits, etc.
       anidados bajo sus claves correspondientes).
    2. Agrega/sobrescribe claves planas (gap_ahead, damage_aero, …) en el
       primer nivel del dict, simulando el formato que evaluate() espera.
    """
    d = base_state.model_dump(mode="json")
    d.update(overrides)
    return d


# =========================================================================
# Tests — Pipeline de alertas 20Hz
# =========================================================================

class TestPipelineSpotterAlerts:
    """Integración: evalúa el pipeline completo evaluate_tick → broadcast."""

    def test_spotter_alert_pit_limiter_active(
        self, spotter, broadcast_messages, base_race_state
    ):
        """in_pitlane=True + pit_limiter_active=False
        → AlertMessage con category='limiter' llega a broadcast."""
        tick = build_tick(base_race_state, in_pits=True, pit_limiter_active=False)
        spotter.evaluate_tick(tick)

        assert len(broadcast_messages) >= 1
        alerts = [
            m for m in broadcast_messages
            if isinstance(m, AlertMessage) and m.category == "limiter"
        ]
        assert len(alerts) >= 1
        assert "Pit limiter no activado" in alerts[0].message
        assert alerts[0].payload.get("severity") == "CRITICAL"
        assert isinstance(alerts[0], AlertMessage)

    def test_spotter_alert_gap_ahead_close(
        self, spotter, broadcast_messages, base_race_state
    ):
        """gap_ahead=0.3 (< 0.5s)
        → AlertMessage con category='gaps' llega a broadcast."""
        tick = build_tick(base_race_state, gap_ahead=0.3)
        spotter.evaluate_tick(tick)

        assert len(broadcast_messages) >= 1
        alerts = [
            m for m in broadcast_messages
            if isinstance(m, AlertMessage) and m.category == "gaps"
        ]
        assert len(alerts) >= 1
        assert "Gap con coche de delante estrecho" in alerts[0].message
        assert isinstance(alerts[0], AlertMessage)

    def test_spotter_alert_damage_detected(
        self, spotter, broadcast_messages, base_race_state
    ):
        """damage_aero=0.5 (> 0.0)
        → AlertMessage con category='damage' llega a broadcast."""
        tick = build_tick(base_race_state, damage_aero=0.5)
        spotter.evaluate_tick(tick)

        assert len(broadcast_messages) >= 1
        alerts = [
            m for m in broadcast_messages
            if isinstance(m, AlertMessage) and m.category == "damage"
        ]
        assert len(alerts) >= 1
        assert "Daños detectados" in alerts[0].message
        assert alerts[0].payload.get("severity") == "WARNING"
        assert isinstance(alerts[0], AlertMessage)

    def test_spotter_alert_fuel_critical(
        self, spotter, broadcast_messages, base_race_state
    ):
        """estimated_laps_remaining=0.5 (< 1.0)
        → AlertMessage con category='fuel' llega a broadcast."""
        tick = build_tick(base_race_state, estimated_laps_remaining=0.5)
        spotter.evaluate_tick(tick)

        assert len(broadcast_messages) >= 1
        alerts = [
            m for m in broadcast_messages
            if isinstance(m, AlertMessage) and m.category == "fuel"
        ]
        assert len(alerts) >= 1
        assert "Combustible crítico" in alerts[0].message
        assert alerts[0].payload.get("severity") == "CRITICAL"
        assert isinstance(alerts[0], AlertMessage)

    def test_spotter_alert_safety_car(
        self, spotter, broadcast_messages, base_race_state
    ):
        """safety_car_active=True
        → AlertMessage con category='safety_car' llega a broadcast."""
        tick = build_tick(base_race_state, safety_car_active=True)
        spotter.evaluate_tick(tick)

        assert len(broadcast_messages) >= 1
        alerts = [
            m for m in broadcast_messages
            if isinstance(m, AlertMessage) and m.category == "safety_car"
        ]
        assert len(alerts) >= 1
        assert "Safety car desplegado" in alerts[0].message
        assert alerts[0].payload.get("severity") == "CRITICAL"
        assert isinstance(alerts[0], AlertMessage)

    def test_spotter_alert_broadcast_sync(
        self, spotter, broadcast_messages, base_race_state
    ):
        """Verifica que el AlertMessage originado en evaluate_tick
        llega correctamente al callback de broadcast (broadcast_sync)."""
        tick = build_tick(base_race_state, safety_car_active=True)
        spotter.evaluate_tick(tick)

        assert len(broadcast_messages) >= 1
        msg = broadcast_messages[0]
        assert isinstance(msg, AlertMessage)
        assert msg.event == "alert"
        assert msg.alert_id is not None
        assert len(msg.alert_id) > 0
        assert msg.category is not None
        assert msg.message is not None
        assert msg.payload is not None
