import uuid
from typing import Any, Dict, List
from src.models.messages import AlertMessage


class SpotterService:
    """Spotter determinista de ultra-baja latencia (20Hz / 50ms).
    
    Sin estado interno (stateless).
    """

    def __init__(self, broadcast_callback=None) -> None:
        self.broadcast_callback = broadcast_callback

    def evaluate_tick(self, state: Any) -> None:
        """Convierte el estado de telemetría a dict, evalúa alertas, y las transmite a través de la envoltura sync."""
        tick_dict = {}
        if state is not None:
            if isinstance(state, dict):
                tick_dict = state
            elif hasattr(state, "model_dump"):
                tick_dict = state.model_dump(mode="json")
            elif hasattr(state, "dict"):
                tick_dict = state.dict()
            else:
                try:
                    tick_dict = vars(state)
                except Exception:
                    pass

        alerts = self.evaluate(tick_dict)
        if alerts and self.broadcast_callback:
            for alert in alerts:
                self.broadcast_callback(alert)

    def evaluate(self, tick: dict) -> List[AlertMessage]:
        """Evalúa condiciones deterministas en el tick de telemetría (50ms)."""
        alerts = []

        # 1. Pit limiter no activado al entrar en boxes
        if tick.get("in_pits", False) and not tick.get("pit_limiter_active", False):
            alerts.append(self._create_alert(
                message="Pit limiter no activado al entrar en boxes.",
                severity="CRITICAL",
                audio_priority=4,
                ttl=5,
                dismissable=True,
                category="limiter",
                payload={"in_pits": True, "pit_limiter_active": False}
            ))

        # 2. Pit limiter no desactivado al salir de boxes
        if not tick.get("in_pits", False) and tick.get("pit_limiter_active", False):
            alerts.append(self._create_alert(
                message="Pit limiter no desactivado al salir de boxes.",
                severity="WARNING",
                audio_priority=3,
                ttl=5,
                dismissable=True,
                category="limiter",
                payload={"in_pits": False, "pit_limiter_active": True}
            ))

        # 3. Gap con coche de delante <0.5s
        gap_ahead = tick.get("gap_ahead", 99.0)
        if gap_ahead < 0.5:
            alerts.append(self._create_alert(
                message=f"Gap con coche de delante estrecho: {gap_ahead:.2f}s",
                severity="INFO",
                audio_priority=1,
                ttl=3,
                dismissable=True,
                category="gaps",
                payload={"gap_ahead": gap_ahead}
            ))

        # 4. Gap con coche de detrás <0.5s
        gap_behind = tick.get("gap_behind", 99.0)
        if gap_behind < 0.5:
            alerts.append(self._create_alert(
                message=f"Gap con coche de detrás estrecho: {gap_behind:.2f}s",
                severity="INFO",
                audio_priority=1,
                ttl=3,
                dismissable=True,
                category="gaps",
                payload={"gap_behind": gap_behind}
            ))

        # 5. Daños detectados
        has_damage = (
            tick.get("damage_aero", 0.0) > 0.0 or
            tick.get("suspension_damage", 0.0) > 0.0 or
            (isinstance(tick.get("damage"), dict) and any(v > 0.0 for v in tick.get("damage").values()))
        )
        if has_damage:
            alerts.append(self._create_alert(
                message="Daños detectados en el monoplaza.",
                severity="WARNING",
                audio_priority=3,
                ttl=10,
                dismissable=True,
                category="damage",
                payload={
                    "damage_aero": tick.get("damage_aero", 0.0),
                    "suspension_damage": tick.get("suspension_damage", 0.0)
                }
            ))

        # 6. Safety car desplegado
        sc_active = tick.get("safety_car_active", False) or tick.get("full_course_yellow_active", False)
        if sc_active:
            alerts.append(self._create_alert(
                message="Safety car desplegado / FCY activo en pista.",
                severity="CRITICAL",
                audio_priority=4,
                ttl=15,
                dismissable=False,
                category="safety_car",
                payload={"safety_car_active": True}
            ))

        # 7. Última vuelta
        is_last_lap = tick.get("session_laps_left") == 1.0 or tick.get("is_last_lap", False)
        if is_last_lap:
            alerts.append(self._create_alert(
                message="¡Última vuelta de la carrera!",
                severity="HIGH",
                audio_priority=2,
                ttl=10,
                dismissable=True,
                category="session",
                payload={"session_laps_left": 1.0}
            ))

        # 8. Combustible para <1 vuelta
        fuel_laps = tick.get("fuel_laps_remaining", tick.get("estimated_laps_remaining", 99.0))
        if fuel_laps < 1.0:
            alerts.append(self._create_alert(
                message=f"¡Combustible crítico! Menos de 1 vuelta restante ({fuel_laps:.2f} laps).",
                severity="CRITICAL",
                audio_priority=4,
                ttl=10,
                dismissable=False,
                category="fuel",
                payload={"fuel_laps_remaining": fuel_laps}
            ))

        return alerts

    def _create_alert(
        self,
        message: str,
        severity: str,
        audio_priority: int,
        ttl: int,
        dismissable: bool,
        category: str,
        payload: Dict[str, Any]
    ) -> AlertMessage:
        return AlertMessage(
            event="alert",
            alert_id=str(uuid.uuid4()),
            category=category,
            message=message,
            audio_priority=str(audio_priority),
            severity=severity,
            ttl=ttl,
            dismissable=dismissable,
            payload={
                "severity": severity,
                "ttl": ttl,
                "dismissable": dismissable,
                **payload
            }
        )
