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
    return SpotterService(
        broadcast_callback=mock_broadcast,
        pit_limiter_grace_s=0.0,
        pit_limiter_exit_check_s=0.0,
    )


def _moving_tick(base: dict, *, in_pits: bool = False, limiter: bool = False) -> dict:
    tick = dict(base)
    tick["in_pits"] = in_pits
    tick["pit_limiter_active"] = limiter
    tick["vel_x"] = 12.0
    tick["vel_y"] = 0.0
    tick["vel_z"] = 0.0
    return tick


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
        tick = _moving_tick(normal_tick, in_pits=True, limiter=False)
        alerts = spotter.evaluate(tick)
        limiter_alerts = [a for a in alerts if a.category == "limiter"]
        assert len(limiter_alerts) >= 1
        assert limiter_alerts[0].payload.get("limiter_event") == "engage"
        assert limiter_alerts[0].payload.get("severity") == "CRITICAL"

    def test_pit_limiter_not_deactivated_exiting_pits(self, spotter, normal_tick):
        """Pit limiter activado al salir de boxes debe generar alerta WARNING."""
        tick_in = _moving_tick(normal_tick, in_pits=True, limiter=True)
        spotter.evaluate(tick_in)
        tick = _moving_tick(normal_tick, in_pits=False, limiter=True)
        alerts = spotter.evaluate(tick)
        limiter_alerts = [a for a in alerts if a.category == "limiter"]
        assert len(limiter_alerts) >= 1
        assert limiter_alerts[0].payload.get("limiter_event") == "disengage"
        assert limiter_alerts[0].payload.get("severity") == "WARNING"

    def test_pit_limiter_exit_waits_cc_delay(self, mock_broadcast, normal_tick):
        """CC: disengage_limiter tras 2 s fuera de boxes con limiter ON."""
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            pit_limiter_grace_s=0.0,
            pit_limiter_exit_check_s=2.0,
        )
        spotter.evaluate(_moving_tick(normal_tick, in_pits=True, limiter=True))
        exit_tick = _moving_tick(normal_tick, in_pits=False, limiter=True)
        assert not any(a.category == "limiter" for a in spotter.evaluate(exit_tick))
        import time as time_mod

        time_mod.sleep(2.05)
        delayed = spotter.evaluate(exit_tick)
        assert any(
            a.category == "limiter" and a.payload.get("limiter_event") == "disengage"
            for a in delayed
        )

    def test_pit_limiter_silent_when_stopped_in_pits(self, spotter, normal_tick):
        tick = _moving_tick(normal_tick, in_pits=True, limiter=False)
        tick["vel_x"] = 0.0
        tick["vel_y"] = 0.0
        tick["vel_z"] = 0.0
        assert not any(a.category == "limiter" for a in spotter.evaluate(tick))

    def test_pit_limiter_active_in_qualifying(self, mock_broadcast, normal_tick):
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            pit_limiter_grace_s=0.0,
            pit_limiter_exit_check_s=0.0,
            spotter_off_qualifying=True,
        )
        tick = _moving_tick(normal_tick, in_pits=True, limiter=False)
        tick["session_type"] = "qualifying"
        assert any(a.category == "limiter" for a in spotter.evaluate(tick))

    def test_pit_limiter_suppressed_if_limiter_seen_during_grace(self, spotter, normal_tick):
        tick = _moving_tick(normal_tick, in_pits=True, limiter=False)
        spotter.evaluate(tick)
        tick["pit_limiter_active"] = True
        spotter.evaluate(tick)
        tick["pit_limiter_active"] = False
        for _ in range(20):
            assert not any(
                a.category == "limiter" and a.payload.get("limiter_event") == "engage"
                for a in spotter.evaluate(tick)
            )

    def test_pit_limiter_not_alert_deep_in_pits(self, mock_broadcast, normal_tick):
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            pit_limiter_grace_s=0.0,
            pit_limiter_exit_check_s=0.0,
            pit_limiter_entry_window_s=0.5,
        )
        tick = _moving_tick(normal_tick, in_pits=True, limiter=False)
        spotter.evaluate(tick)
        import time as time_mod

        time_mod.sleep(0.6)
        assert not any(
            a.category == "limiter" and a.payload.get("limiter_event") == "engage"
            for a in spotter.evaluate(tick)
        )

    def test_pit_limiter_disengage_when_limiter_off_on_exit_edge(self, spotter, normal_tick):
        """LMU puede marcar limiter=false al cruzar salida; usamos histórico de la parada."""
        tick_in = _moving_tick(normal_tick, in_pits=True, limiter=True)
        spotter.evaluate(tick_in)
        for _ in range(5):
            spotter.evaluate(_moving_tick(normal_tick, in_pits=True, limiter=True))
        tick_out = _moving_tick(normal_tick, in_pits=False, limiter=False)
        spotter.evaluate(tick_out)
        tick_out["pit_limiter_active"] = True
        import time as time_mod

        time_mod.sleep(0.55)
        delayed = spotter.evaluate(tick_out)
        assert any(
            a.payload.get("limiter_event") == "disengage" for a in delayed if a.category == "limiter"
        )

    def test_pit_limiter_engage_cooldown_does_not_block_disengage(self, mock_broadcast, normal_tick):
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            pit_limiter_grace_s=0.0,
            pit_limiter_exit_check_s=0.0,
        )
        spotter.evaluate(_moving_tick(normal_tick, in_pits=True, limiter=False))
        spotter.evaluate(_moving_tick(normal_tick, in_pits=True, limiter=True))
        tick_out = _moving_tick(normal_tick, in_pits=False, limiter=True)
        alerts = spotter.evaluate(tick_out)
        assert any(a.payload.get("limiter_event") == "disengage" for a in alerts if a.category == "limiter")

    def test_pit_limiter_enter_survives_in_pits_flicker(self, spotter, normal_tick):
        """Flicker de in_pits no debe repetir la alerta de entrada en boxes."""
        tick_in = _moving_tick(normal_tick, in_pits=True, limiter=False)
        tick_out = _moving_tick(normal_tick, in_pits=False, limiter=False)
        all_limiter: list = []
        all_limiter.extend(a for a in spotter.evaluate(tick_in) if a.category == "limiter")
        spotter.evaluate(tick_out)
        for _ in range(20):
            all_limiter.extend(a for a in spotter.evaluate(tick_in) if a.category == "limiter")
        assert len(all_limiter) == 1

    def test_pit_limiter_enter_survives_limiter_flicker(self, spotter, normal_tick):
        """Parpadeo del limiter en LMU no debe repetir la alerta de entrada."""
        tick = _moving_tick(normal_tick, in_pits=True, limiter=False)
        all_limiter: list = []
        all_limiter.extend(a for a in spotter.evaluate(tick) if a.category == "limiter")
        for i in range(1, 50):
            t = dict(tick)
            if i % 5 == 0:
                t["pit_limiter_active"] = True
            all_limiter.extend(a for a in spotter.evaluate(t) if a.category == "limiter")
        assert len(all_limiter) == 1

    def test_pit_limiter_enter_does_not_spam(self, spotter, normal_tick):
        """En boxes sin limiter: una sola alerta aunque evaluate() se llame muchas veces."""
        tick = _moving_tick(normal_tick, in_pits=True, limiter=False)
        all_limiter: list = []
        for _ in range(50):
            all_limiter.extend(a for a in spotter.evaluate(tick) if a.category == "limiter")
        assert len(all_limiter) == 1

    def test_gap_ahead_less_than_05s(self, spotter, normal_tick):
        """Gap con coche de delante < 0.5s debe generar alerta de tráfico."""
        spotter.apply_runtime_config({"enableGapMessages": False})
        tick = dict(normal_tick)
        tick["gap_ahead"] = 0.3
        alerts = spotter.evaluate(tick)
        gap_alerts = [a for a in alerts if a.category == "gaps"]
        assert len(gap_alerts) >= 1
        assert "Gap con coche de delante estrecho" in gap_alerts[0].message

    def test_gap_behind_less_than_05s(self, spotter, normal_tick):
        """Gap con coche de detrás < 0.5s debe generar alerta."""
        spotter.apply_runtime_config({"enableGapMessages": False})
        tick = dict(normal_tick)
        tick["gap_behind"] = 0.2
        alerts = spotter.evaluate(tick)
        gap_alerts = [a for a in alerts if a.category == "gaps"]
        assert len(gap_alerts) >= 1
        assert "Gap con coche de detrás estrecho" in gap_alerts[0].message

    def test_damage_not_emitted_by_spotter(self, spotter, normal_tick):
        """Daño lo emite el módulo Crew Chief engineer, no el spotter."""
        tick = dict(normal_tick)
        tick["damage_aero"] = 0.15
        alerts = spotter.evaluate(tick)
        damage_alerts = [a for a in alerts if a.category == "damage"]
        assert len(damage_alerts) == 0

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
        spotter.apply_runtime_config({"enableLapCounterMessages": False})
        tick = dict(normal_tick)
        tick["session_laps_left"] = 1.0
        alerts = spotter.evaluate(tick)
        session_alerts = [a for a in alerts if a.category == "session"]
        assert len(session_alerts) >= 1
        assert "Última vuelta" in session_alerts[0].message

    def test_critical_fuel_alert(self, spotter, normal_tick):
        """Menos de 1 vuelta de combustible debe generar alerta CRITICAL."""
        spotter.apply_runtime_config({"enableFuelMessages": False})
        tick = dict(normal_tick)
        tick["estimated_laps_remaining"] = 0.5
        tick["fuel_laps_remaining"] = 0.5
        tick["pit_stops_needed"] = 1
        alerts = spotter.evaluate(tick)
        fuel_alerts = [a for a in alerts if a.category == "fuel"]
        assert len(fuel_alerts) >= 1
        assert "Combustible crítico" in fuel_alerts[0].message

    def test_no_fuel_alert_when_finish_on_current_fuel(self, spotter, normal_tick):
        tick = dict(normal_tick)
        tick["estimated_laps_remaining"] = 0.8
        tick["fuel_laps_remaining"] = 0.8
        tick["session_laps_left"] = 0.5
        tick["pit_stops_needed"] = 0
        tick["fuel_in_tank"] = 30.0
        tick["fuel_needed_to_finish"] = 25.0
        alerts = spotter.evaluate(tick)
        assert not any(a.category == "fuel" for a in alerts)

    def test_qualifying_silent_no_proximity(self, mock_broadcast):
        """CC: sin lateral en quali; limiter/SC/fuel siguen activos."""
        from tests.test_spotter_proximity_pipeline import make_side_by_side_race_frame
        from src.intelligence.spotter_adapter import frame_to_spotter_tick

        frame = make_side_by_side_race_frame()
        frame["session_type"] = "qualifying"
        tick = frame_to_spotter_tick(frame)
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            spotter_off_qualifying=True,
            proximity_threshold_m=3.0,
        )
        race_alerts = spotter.evaluate(frame_to_spotter_tick(make_side_by_side_race_frame()))
        assert any(a.category == "proximity" for a in race_alerts)

        quali_alerts = spotter.evaluate(tick)
        assert not any(a.category == "proximity" for a in quali_alerts)
        assert not any(a.category == "gaps" for a in quali_alerts)

    def test_fuel_sc_last_lap_damage_do_not_spam(self, spotter, normal_tick):
        spotter.apply_runtime_config({"enableLapCounterMessages": False, "enableFuelMessages": False})
        tick = dict(normal_tick)
        tick["estimated_laps_remaining"] = 0.4
        tick["safety_car_active"] = True
        tick["session_laps_left"] = 1.0
        tick["damage_aero"] = 0.2
        counts: dict[str, int] = {}
        for _ in range(40):
            for alert in spotter.evaluate(tick):
                counts[alert.category] = counts.get(alert.category, 0) + 1
        assert counts.get("fuel", 0) == 1
        assert counts.get("safety_car", 0) == 1
        assert counts.get("session", 0) == 1
        assert counts.get("damage", 0) == 0

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
        spotter.apply_runtime_config({"enableFuelMessages": False})
        tick = _moving_tick(normal_tick, in_pits=True, limiter=False)
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
