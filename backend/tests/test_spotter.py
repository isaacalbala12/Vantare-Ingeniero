"""
Tests unitarios para el SpotterService de ultra-baja latencia.

Verifica:
- Las 8 condiciones deterministas se evalúan correctamente.
- Se emiten AlertMessage cuando corresponde.
- No se emiten alertas cuando las condiciones son normales.
"""
import pytest
from src.intelligence.spotter import SpotterService
from src.models.messages import AlertMessage


@pytest.fixture
def spotter(mock_broadcast):
    return SpotterService(broadcast_callback=mock_broadcast)


@pytest.fixture
def normal_tick():
    """Tick de telemetría sin condiciones de alerta."""
    return {
        "in_pits": False,
        "pit_limiter_active": False,
        "gap_ahead": 5.0,
        "gap_behind": 5.0,
        "damage_aero": 0.0,
        "suspension_damage": 0.0,
        "safety_car_active": False,
        "full_course_yellow_active": False,
        "session_laps_left": 10.0,
        "estimated_laps_remaining": 10.0,
    }


class TestSpotterEvaluate:
    """Prueba el método evaluate() del spotter."""

    def test_no_alerts_on_normal_state(self, spotter, normal_tick):
        """Con un tick normal, evaluate() no debe generar alertas."""
        alerts = spotter.evaluate(normal_tick)
        assert len(alerts) == 0

    def test_pit_limiter_not_activated_entering_pits(self, spotter, normal_tick):
        """Pit limiter no activado al entrar en boxes debe generar alerta CRITICAL."""
        tick = dict(normal_tick)
        tick["in_pits"] = True
        tick["pit_limiter_active"] = False
        alerts = spotter.evaluate(tick)
        assert len(alerts) >= 1
        limiter_alerts = [a for a in alerts if a.category == "limiter"]
        assert len(limiter_alerts) >= 1
        assert "Pit limiter no activado" in limiter_alerts[0].message
        assert limiter_alerts[0].payload.get("severity") == "CRITICAL"

    def test_pit_limiter_not_deactivated_exiting_pits(self, spotter, normal_tick):
        """Pit limiter activado al salir de boxes debe generar alerta WARNING."""
        tick = dict(normal_tick)
        tick["in_pits"] = False
        tick["pit_limiter_active"] = True
        alerts = spotter.evaluate(tick)
        limiter_alerts = [a for a in alerts if a.category == "limiter"]
        assert len(limiter_alerts) >= 1
        assert "Pit limiter no desactivado" in limiter_alerts[0].message
        assert limiter_alerts[0].payload.get("severity") == "WARNING"

    def test_gap_ahead_less_than_05s(self, spotter, normal_tick):
        """Gap con coche de delante < 0.5s debe generar alerta de tráfico."""
        tick = dict(normal_tick)
        tick["gap_ahead"] = 0.3
        alerts = spotter.evaluate(tick)
        gap_alerts = [a for a in alerts if a.category == "gaps"]
        assert len(gap_alerts) >= 1
        assert "Gap con coche de delante estrecho" in gap_alerts[0].message

    def test_gap_behind_less_than_05s(self, spotter, normal_tick):
        """Gap con coche de detrás < 0.5s debe generar alerta."""
        tick = dict(normal_tick)
        tick["gap_behind"] = 0.2
        alerts = spotter.evaluate(tick)
        gap_alerts = [a for a in alerts if a.category == "gaps"]
        assert len(gap_alerts) >= 1
        assert "Gap con coche de detrás estrecho" in gap_alerts[0].message

    def test_damage_detected(self, spotter, normal_tick):
        """Daño aero > 0 debe generar alerta de daños."""
        tick = dict(normal_tick)
        tick["damage_aero"] = 0.15
        alerts = spotter.evaluate(tick)
        damage_alerts = [a for a in alerts if a.category == "damage"]
        assert len(damage_alerts) >= 1
        assert "Daños detectados" in damage_alerts[0].message

    def test_safety_car_deployed(self, spotter, normal_tick):
        """Safety car activo debe generar alerta CRITICAL."""
        tick = dict(normal_tick)
        tick["safety_car_active"] = True
        alerts = spotter.evaluate(tick)
        sc_alerts = [a for a in alerts if a.category == "safety_car"]
        assert len(sc_alerts) >= 1
        assert "Safety car desplegado" in sc_alerts[0].message
        assert sc_alerts[0].payload.get("severity") == "CRITICAL"

    def test_fcy_detected(self, spotter, normal_tick):
        """Full Course Yellow debe generar alerta."""
        tick = dict(normal_tick)
        tick["full_course_yellow_active"] = True
        alerts = spotter.evaluate(tick)
        sc_alerts = [a for a in alerts if a.category == "safety_car"]
        assert len(sc_alerts) >= 1

    def test_last_lap_alert(self, spotter, normal_tick):
        """Última vuelta debe generar alerta HIGH."""
        tick = dict(normal_tick)
        tick["session_laps_left"] = 1.0
        alerts = spotter.evaluate(tick)
        session_alerts = [a for a in alerts if a.category == "session"]
        assert len(session_alerts) >= 1
        assert "Última vuelta" in session_alerts[0].message

    def test_critical_fuel_alert(self, spotter, normal_tick):
        """Menos de 1 vuelta de combustible debe generar alerta CRITICAL."""
        tick = dict(normal_tick)
        tick["estimated_laps_remaining"] = 0.5
        alerts = spotter.evaluate(tick)
        fuel_alerts = [a for a in alerts if a.category == "fuel"]
        assert len(fuel_alerts) >= 1
        assert "Combustible crítico" in fuel_alerts[0].message

    def test_alert_message_structure(self, spotter, normal_tick):
        """Las alertas deben ser instancias de AlertMessage con campos obligatorios."""
        tick = dict(normal_tick)
        tick["safety_car_active"] = True
        alerts = spotter.evaluate(tick)
        assert len(alerts) >= 1
        alert = alerts[0]
        assert isinstance(alert, AlertMessage)
        assert alert.event == "alert"
        assert alert.alert_id is not None and len(alert.alert_id) > 0
        assert alert.category is not None
        assert alert.message is not None

    def test_multiple_alerts_simultaneously(self, spotter, normal_tick):
        """Múltiples condiciones activas deben generar múltiples alertas."""
        tick = dict(normal_tick)
        tick["in_pits"] = True
        tick["pit_limiter_active"] = False
        tick["safety_car_active"] = True
        tick["estimated_laps_remaining"] = 0.3
        alerts = spotter.evaluate(tick)
        categories = {a.category for a in alerts}
        assert "limiter" in categories
        assert "safety_car" in categories
        assert "fuel" in categories


class TestSpotterEvaluateTick:
    """Prueba el método evaluate_tick() que convierte estado a dict."""

    def test_evaluate_tick_with_pydantic_model(self, spotter, broadcast_messages, mock_race_state):
        """evaluate_tick debe aceptar un objeto Pydantic y emitir broadcast si hay alertas."""
        # Modificar el estado para que active safety car
        mock_race_state.session.session_type = 6  # game phase for SC
        spotter.evaluate_tick(mock_race_state)
        # No necesariamente hay alertas, pero no debe lanzar error

    def test_evaluate_tick_with_dict(self, spotter, broadcast_messages, normal_tick):
        """evaluate_tick debe aceptar un dict directamente."""
        tick = dict(normal_tick)
        tick["safety_car_active"] = True
        spotter.evaluate_tick(tick)
        # Debe haber broadcasts de alerta
        assert len(broadcast_messages) >= 1
        assert any(isinstance(m, AlertMessage) for m in broadcast_messages)

    def test_evaluate_tick_no_broadcast_without_alerts(self, spotter, broadcast_messages, normal_tick):
        """Sin alertas, no debe haber broadcasts."""
        spotter.evaluate_tick(normal_tick)
        assert len(broadcast_messages) == 0
