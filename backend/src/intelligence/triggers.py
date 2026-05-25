import logging
import time
from enum import Enum
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger("vantare.triggers")

class TriggerAction(str, Enum):
    LLM_REQUIRED = "LLM_REQUIRED"
    DETERMINISTIC_ONLY = "DETERMINISTIC_ONLY"
    ALERT_ONLY = "ALERT_ONLY"

class Priority(int, Enum):
    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1

class ContextTier(str, Enum):
    FAST = "FAST"
    STANDARD = "STANDARD"
    DEEP = "DEEP"

class BaseTrigger(ABC):
    """Clase base para todos los triggers de la capa de inteligencia."""

    def __init__(
        self,
        priority: Priority,
        tier: ContextTier,
        action: TriggerAction,
        min_interval: float,
        description: str,
        alert_text: str
    ) -> None:
        self.priority = priority
        self.tier = tier
        self.action = action
        self.min_interval = min_interval
        self.description = description
        self.alert_text = alert_text
        self.last_triggered: float = 0.0
        self.name = description

    def should_evaluate(self, current_time: Optional[float] = None) -> bool:
        """Controla el cooldown con detección de time jumps (hibernación/suspensión)."""
        now = current_time if current_time is not None else time.monotonic()
        elapsed = now - self.last_triggered

        # Detectar time jump: si pasó más de 3x el intervalo, es una suspensión
        if elapsed > self.min_interval * 3 and self.last_triggered > 0:
            logger.debug("Time jump detectado en trigger '%s': %.0fs", self.description, elapsed)
            self.last_triggered = now
            return False

        return elapsed >= self.min_interval

    def mark_triggered(self, current_time: Optional[float] = None) -> None:
        """Marca el timestamp de activación."""
        self.last_triggered = current_time if current_time is not None else time.monotonic()

    @abstractmethod
    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        """Evalúa las condiciones físicas en la telemetría viva."""
        pass


# =====================================================================
# IMPLEMENTACIÓN DE LOS 12 TRIGGERS CONSOLIDADOS
# =====================================================================

class FuelCriticalTrigger(BaseTrigger):
    """Trigger 1: Combustible críticamente bajo (< 3 vueltas de autonomía)."""
    def __init__(self) -> None:
        super().__init__(
            Priority.CRITICAL,
            ContextTier.FAST,
            TriggerAction.LLM_REQUIRED,
            min_interval=15.0,
            description="Combustible críticamente bajo",
            alert_text="¡ATENCIÓN! Quedan menos de 3 vueltas de combustible. Planifica parada."
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        fuel = strategy.get("fuel") or {}
        est_laps = fuel.get("estimated_laps_remaining", 99.0)
        return est_laps < 3.0 and not telemetry.get("in_pits", False)


class SafetyCarTrigger(BaseTrigger):
    """Trigger 2: Coche de Seguridad (Safety Car) o Full Course Yellow activo."""
    def __init__(self) -> None:
        super().__init__(
            Priority.CRITICAL,
            ContextTier.FAST,
            TriggerAction.LLM_REQUIRED,
            min_interval=10.0,
            description="Safety Car o FCY desplegado",
            alert_text="¡SAFETY CAR o FCY ACTIVO! Reduce velocidad y prepárate."
        )
        self.name = "Safety Car Active"

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        sc_active = telemetry.get("safety_car_active", False)
        fcy_active = telemetry.get("full_course_yellow_active", False)
        return sc_active or fcy_active


class BrakeWearCriticalTrigger(BaseTrigger):
    """Trigger 3: Desgaste crítico de frenos (> 80% en alguna rueda)."""
    def __init__(self) -> None:
        super().__init__(
            Priority.CRITICAL,
            ContextTier.FAST,
            TriggerAction.ALERT_ONLY,
            min_interval=20.0,
            description="Desgaste crítico de frenos",
            alert_text="¡AVISO DE FRENOS! Desgaste superior al 80% detectado."
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        w_fl = telemetry.get("brake_wear_fl", 0.0)
        w_fr = telemetry.get("brake_wear_fr", 0.0)
        w_rl = telemetry.get("brake_wear_rl", 0.0)
        w_rr = telemetry.get("brake_wear_rr", 0.0)
        return any(w > 80.0 for w in [w_fl, w_fr, w_rl, w_rr])


class TyreDegAccelTrigger(BaseTrigger):
    """Trigger 4: Degradación acelerada en neumáticos (> 25% de desgaste promedio)."""
    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.STANDARD,
            TriggerAction.LLM_REQUIRED,
            min_interval=30.0,
            description="Degradación de neumáticos acelerada",
            alert_text="Desgaste promedio de neumáticos elevado. Ritmo degradado."
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        w_fl = telemetry.get("tyre_wear_fl", 0.0)
        w_fr = telemetry.get("tyre_wear_fr", 0.0)
        w_rl = telemetry.get("tyre_wear_rl", 0.0)
        w_rr = telemetry.get("tyre_wear_rr", 0.0)
        avg_wear = (w_fl + w_fr + w_rl + w_rr) / 4.0
        return avg_wear > 25.0 and not telemetry.get("in_pits", False)


class HybridDeployMapTrigger(BaseTrigger):
    """Trigger 5: Batería baja (< 20%) y tendencia de descarga neta negativa."""
    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.STANDARD,
            TriggerAction.LLM_REQUIRED,
            min_interval=30.0,
            description="Estado SOC híbrido crítico",
            alert_text="Carga de batería híbrida baja. Optimiza mapeo para recarga."
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        charge = telemetry.get("battery_charge", 100.0)
        drain = telemetry.get("battery_drain", 0.0)
        regen = telemetry.get("battery_regen", 0.0)
        net_trend = regen - drain
        return charge < 20.0 and net_trend < 0.0


class WeatherChangeTrigger(BaseTrigger):
    """Trigger 6: Cambio climático inminente (Probabilidad de lluvia > 30% en los próximos 30 minutos)."""
    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.DEEP,
            TriggerAction.LLM_REQUIRED,
            min_interval=120.0,
            description="Amenaza de lluvia inminente",
            alert_text="Probabilidad de lluvia superior al 30% en el forecast actual."
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        weather_list = session.get("weather_forecast", [])
        if not isinstance(weather_list, list) or not weather_list:
            return False
        # Evaluar los primeros nodos de previsión (ej: NODE_25, NODE_50)
        for slot in weather_list[:2]:
            if isinstance(slot, dict):
                rain_chance = float(slot.get("WNV_RAIN_CHANCE", 0.0))
                if rain_chance > 30.0:
                    return True
        return False


class PitWindowOpenedTrigger(BaseTrigger):
    """Trigger 7: Ventana de paradas en boxes abierta."""
    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.STANDARD,
            TriggerAction.LLM_REQUIRED,
            min_interval=30.0,
            description="Ventana de parada abierta",
            alert_text="Ventana de paradas activa. Analizando estrategia óptima."
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        pit_window = strategy.get("pit_window") or {}
        return pit_window.get("pit_window_open", False) and not telemetry.get("in_pits", False)


class PitWindowClosingTrigger(BaseTrigger):
    """Trigger 8: Ventana de paradas cerrándose (quedan <= 2 vueltas de ventana abierta)."""
    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.FAST,
            TriggerAction.LLM_REQUIRED,
            min_interval=15.0,
            description="Ventana de parada cerrándose",
            alert_text="Ventana de boxes a punto de cerrar. Parada obligatoria inminente."
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        pit_window = strategy.get("pit_window") or {}
        window_open = pit_window.get("pit_window_open", False)
        laps_remaining_in_window = pit_window.get("optimal_pit_lap", 0) - telemetry.get("lap_number", 0)
        return window_open and 0 <= laps_remaining_in_window <= 2 and not telemetry.get("in_pits", False)


class CompetitorPittedTrigger(BaseTrigger):
    """Trigger 9: Un competidor directo (posición contigua) entra a boxes."""
    def __init__(self) -> None:
        super().__init__(
            Priority.MEDIUM,
            ContextTier.STANDARD,
            TriggerAction.LLM_REQUIRED,
            min_interval=15.0,
            description="Competidor directo en boxes",
            alert_text="Rival directo parado en boxes. Oportunidad de undercut/overcut."
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        competitors = telemetry.get("competitors", [])
        my_pos = telemetry.get("standing_position", 1)
        if not isinstance(competitors, list):
            return False
        for c in competitors:
            if isinstance(c, dict):
                pos = c.get("standing_position", 99)
                # Rival a +/- 1 posición que entra en pits
                if abs(pos - my_pos) == 1 and c.get("in_pits", False):
                    return True
        return False


class GapClosedTrigger(BaseTrigger):
    """Trigger 10: Brecha con el coche de delante o detrás inferior a 1.5s."""
    def __init__(self) -> None:
        super().__init__(
            Priority.MEDIUM,
            ContextTier.FAST,
            TriggerAction.LLM_REQUIRED,
            min_interval=10.0,
            description="Brecha cerrada con rival",
            alert_text="Brecha menor a 1.5 segundos. Entrando en zona de batalla táctica."
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        gap_ahead = telemetry.get("gap_ahead", 99.0)
        gap_behind = telemetry.get("gap_behind", 99.0)
        return (gap_ahead < 1.5 or gap_behind < 1.5) and not telemetry.get("in_pits", False)


class PhaseChangedTrigger(BaseTrigger):
    """Trigger 11: Cambio en la fase de carrera (ej: paso de clasificación a carrera, o bandera roja)."""
    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.FAST,
            TriggerAction.LLM_REQUIRED,
            min_interval=5.0,
            description="Cambio de fase de carrera",
            alert_text="Fase de carrera actualizada. Re-evaluando estrategia."
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        # Usamos un atributo persistente para rastrear el cambio de fase
        current_phase = session.get("phase") or telemetry.get("session_type", "RACE")
        if not hasattr(self, "_last_phase"):
            self._last_phase = current_phase
            return False
        if current_phase != self._last_phase:
            self._last_phase = current_phase
            return True
        return False


class PilotQuestionTrigger(BaseTrigger):
    """Trigger 12: Pregunta explícita formulada por el piloto."""
    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.DEEP,
            TriggerAction.LLM_REQUIRED,
            min_interval=0.0,  # Sin cooldown para interacción interactiva por voz
            description="Pregunta directa del piloto",
            alert_text="Procesando consulta directa por radio..."
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        # Este trigger se dispara de forma manual/explícita en el engine
        return False


class TiresThermalOverheatingTrigger(BaseTrigger):
    """Trigger de temperatura excesiva de neumáticos para compatibilidad con test_preemption."""
    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.STANDARD,
            TriggerAction.LLM_REQUIRED,
            min_interval=30.0,
            description="Temperatura excesiva de neumáticos",
            alert_text="¡ATENCIÓN! Temperatura de neumáticos elevada."
        )
        self.name = "Tires Thermal Overheating"

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        t_fl = telemetry.get("tyre_temp_fl", 0.0)
        t_fr = telemetry.get("tyre_temp_fr", 0.0)
        t_rl = telemetry.get("tyre_temp_rl", 0.0)
        t_rr = telemetry.get("tyre_temp_rr", 0.0)
        return any(t > 105.0 for t in [t_fl, t_fr, t_rl, t_rr])


def get_all_triggers() -> list[BaseTrigger]:
    """Retorna la lista de los 12 triggers ordenados por prioridad descendente."""
    return [
        FuelCriticalTrigger(),
        SafetyCarTrigger(),
        BrakeWearCriticalTrigger(),
        TiresThermalOverheatingTrigger(),
        TyreDegAccelTrigger(),
        HybridDeployMapTrigger(),
        WeatherChangeTrigger(),
        PitWindowOpenedTrigger(),
        PitWindowClosingTrigger(),
        CompetitorPittedTrigger(),
        GapClosedTrigger(),
        PhaseChangedTrigger(),
        PilotQuestionTrigger()
    ]
