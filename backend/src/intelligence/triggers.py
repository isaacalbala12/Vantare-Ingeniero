import logging
import time
from abc import ABC, abstractmethod
from enum import Enum, StrEnum

from src.intelligence.crewchief_events.cc_gates import session_enable_flag
from src.intelligence.gaps import resolve_gaps
from src.intelligence.state_coercion import lmu_scalar

logger = logging.getLogger("vantare.triggers")


def telemetry_on_track(telemetry: dict) -> bool:
    """Evita triggers LLM en boxes, parrilla o telemetría estática."""
    if telemetry.get("in_pits", False):
        return False
    lap = int(lmu_scalar(telemetry.get("lap_number"), default=0))
    speed = float(lmu_scalar(telemetry.get("speed"), default=0.0))
    return lap >= 1 and speed >= 8.0


def _flags_cc_owned(session: dict) -> bool:
    if "enable_flag_messages" in session:
        return bool(session["enable_flag_messages"])
    return session_enable_flag(session, "enable_fcy_messages", True)


def _legacy_on_track(telemetry: dict) -> bool:
    """Condición mínima para tests unitarios con telemetría parcial."""
    if telemetry.get("in_pits", False):
        return False
    if "speed" not in telemetry:
        return True
    return telemetry_on_track(telemetry)


class TriggerAction(StrEnum):
    LLM_REQUIRED = "LLM_REQUIRED"
    DETERMINISTIC_ONLY = "DETERMINISTIC_ONLY"
    ALERT_ONLY = "ALERT_ONLY"


class Priority(int, Enum):
    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1


class ContextTier(StrEnum):
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
        alert_text: str,
        phrase_key: str | None = None,
    ) -> None:
        self.priority = priority
        self.tier = tier
        self.action = action
        self.min_interval = min_interval
        self.description = description
        self.alert_text = alert_text
        self.phrase_key = phrase_key
        self.last_triggered: float = 0.0
        self.name = description
        self._edge_latched = False

    def resolve_message(self, personality) -> str:
        if not self.phrase_key:
            return self.alert_text
        from src.intelligence.phrase_picker import PhrasePicker

        picker = PhrasePicker.load_defaults()
        msg = picker.trigger_phrase(self.phrase_key, profile_id=personality.profile_id)
        return msg or self.alert_text

    def _fire_rising_edge(self, active: bool) -> bool:
        if not active:
            self._edge_latched = False
            return False
        if self._edge_latched:
            return False
        self._edge_latched = True
        return True

    def should_evaluate(self, current_time: float | None = None) -> bool:
        """Controla el cooldown con detección de time jumps (hibernación/suspensión)."""
        now = current_time if current_time is not None else time.monotonic()
        elapsed = now - self.last_triggered

        # Detectar time jump: si pasó más de 3x el intervalo, es una suspensión
        if elapsed > self.min_interval * 3 and self.last_triggered > 0:
            logger.debug("Time jump detectado en trigger '%s': %.0fs", self.description, elapsed)
            self.last_triggered = now
            return False

        return elapsed >= self.min_interval

    def mark_triggered(self, current_time: float | None = None) -> None:
        """Marca el timestamp de activación."""
        self.last_triggered = current_time if current_time is not None else time.monotonic()

    @abstractmethod
    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        """Evalúa las condiciones físicas en la telemetría viva."""
        pass

    def applies(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        """Gating de sesión carrera + condición física (tests y monitores legacy)."""
        from shared_telemetry.session_kind import is_race_session

        if not is_race_session(telemetry, session):
            return False
        return self.condition(telemetry, strategy, session)


# =====================================================================
# IMPLEMENTACIÓN DE LOS 12 TRIGGERS CONSOLIDADOS
# =====================================================================


class FuelCriticalTrigger(BaseTrigger):
    """Trigger 1: Combustible críticamente bajo (< 3 vueltas de autonomía)."""

    def __init__(self) -> None:
        super().__init__(
            Priority.CRITICAL,
            ContextTier.FAST,
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=15.0,
            description="Combustible críticamente bajo",
            alert_text="Fallback combustible bajo.",
            phrase_key="fuel_critical",
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if session_enable_flag(session, "enable_fuel_messages", True):
            return False
        if not _legacy_on_track(telemetry):
            return False
        from src.intelligence.fuel_safety import fuel_critical_from_strategy

        raw = fuel_critical_from_strategy(telemetry, strategy, threshold=3.0)
        return self._fire_rising_edge(raw)


class FlagsMonitorTrigger(BaseTrigger):
    """Trigger 2: Monitor de banderas (SC/FCY/amarilla/azul/roja). Reemplaza SafetyCarTrigger."""

    def __init__(self) -> None:
        super().__init__(
            Priority.CRITICAL,
            ContextTier.FAST,
            TriggerAction.LLM_REQUIRED,
            min_interval=10.0,
            description="Cambio de bandera o SC/FCY activo",
            alert_text="¡SAFETY CAR o FCY ACTIVO! Reduce velocidad y prepárate.",
        )
        self.name = "Flags Monitor"
        self._prev_snapshot = None

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        from src.intelligence.flags_monitor import (
            detect_flag_transitions,
            pick_highest_priority_event,
            snapshot_from_telemetry,
        )

        current = snapshot_from_telemetry(telemetry)
        if self._prev_snapshot is None:
            self._prev_snapshot = current
            return False

        if _flags_cc_owned(session):
            self._prev_snapshot = current
            return False

        transitions = detect_flag_transitions(self._prev_snapshot, current)
        previous = self._prev_snapshot
        self._prev_snapshot = current

        if (current.safety_car or current.fcy) and not (previous.safety_car or previous.fcy):
            self.alert_text = "¡SAFETY CAR o FCY ACTIVO! Reduce velocidad y prepárate."
            return True

        event = pick_highest_priority_event(transitions)
        if event is not None:
            if not telemetry_on_track(telemetry):
                return False
            self.alert_text = event.message
            return True
        return False


# Alias legacy para tests/benchmarks que importen SafetyCarTrigger
SafetyCarTrigger = FlagsMonitorTrigger


_CLASS_RANK = {
    "GT3": 1,
    "LMP3": 2,
    "LMP2": 3,
    "GTE": 3,
    "HYPERCAR": 5,
    "LMH": 5,
    "HY": 5,
}


def _normalize_class(name: str) -> str:
    n = (name or "").upper().replace(" ", "")
    if n in ("HY", "HYPERCAR", "LMH"):
        return "HYPERCAR"
    return n


def _class_rank(name: str) -> int:
    return _CLASS_RANK.get(_normalize_class(name), 2)


class MulticlassWarningTrigger(BaseTrigger):
    """Aviso cuando una clase más rápida se acerca o hay que doblar a una más lenta."""

    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.FAST,
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=8.0,
            description="Proximidad multiclase",
            alert_text="Atención multiclase en pista.",
        )
        self.name = "Multiclass Warning"

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if session_enable_flag(session, "enable_multiclass_messages", True):
            return False
        if telemetry.get("in_pits", False):
            return False

        player_class = telemetry.get("player_class", "")
        player_rank = _class_rank(player_class)
        competitors = strategy.get("competitors") or telemetry.get("competitors") or []
        matched = False

        for comp in competitors:
            if not isinstance(comp, dict):
                continue
            if comp.get("in_pits", False):
                continue

            gap = float(comp.get("gap_to_player", 99.0))
            comp_class = comp.get("driver_class", "")
            comp_rank = _class_rank(comp_class)
            label = _normalize_class(comp_class) or comp_class or "Rival"

            if comp_rank > player_rank and -2.0 <= gap < 0:
                self.alert_text = f"{label} alcanzando — {abs(gap):.1f}s detrás."
                matched = True
                break

            if comp_rank < player_rank and 0 < gap <= 1.0:
                self.alert_text = f"{label} delante, prepárate para doblar."
                matched = True
                break

        return self._fire_rising_edge(matched)


class DriverSwapTrigger(BaseTrigger):
    """Detecta cambio de piloto al volante (endurance)."""

    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.FAST,
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=30.0,
            description="Cambio de piloto detectado",
            alert_text="Cambio de piloto detectado.",
        )
        self.name = "Driver Swap"
        self._last_driver: str = ""

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if session_enable_flag(session, "enable_driver_swap_messages", True):
            return False
        name = str(telemetry.get("driver_name", "") or "").strip()
        if not name:
            return False
        if not self._last_driver:
            self._last_driver = name
            return False
        if name != self._last_driver:
            self.alert_text = f"Cambio de piloto detectado — {name} al volante."
            self._last_driver = name
            return True
        return False


class PenaltyMonitorTrigger(BaseTrigger):
    """Monitor de penalizaciones pendientes y servidas."""

    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.FAST,
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=15.0,
            description="Penalización detectada",
            alert_text="Penalización detectada.",
        )
        self.name = "Penalty Monitor"
        self._last_penalties: int | None = None

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        return False


class PushNowTrigger(BaseTrigger):
    """Modo ataque cuando hay ventana táctica o faltan pocas vueltas."""

    def __init__(self) -> None:
        super().__init__(
            Priority.MEDIUM,
            ContextTier.STANDARD,
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=45.0,
            description="Modo ataque activado",
            alert_text="Modo ataque activado, dale todo.",
        )
        self.name = "Push Now"

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if session_enable_flag(session, "enable_push_now_messages", True):
            return False
        if not _legacy_on_track(telemetry):
            return False
        session_type = str(telemetry.get("session_type", "")).lower()
        if session_type not in ("race", "r"):
            return False

        pit_window = strategy.get("pit_window") or {}
        _, gap_behind = resolve_gaps(telemetry)
        if pit_window.get("undercut_potential") and gap_behind < 2.0:
            self.alert_text = "Modo ataque activado — ventana de undercut, dale todo."
            return self._fire_rising_edge(True)

        laps_left = float(telemetry.get("session_laps_left", 999.0))
        raw = 0 < laps_left <= 3
        if raw:
            self.alert_text = "Modo ataque activado, dale todo — faltan pocas vueltas."
        return self._fire_rising_edge(raw)


class SessionEndTrigger(BaseTrigger):
    """Mensaje de fin de sesión con resumen básico."""

    def __init__(self) -> None:
        super().__init__(
            Priority.MEDIUM,
            ContextTier.STANDARD,
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=60.0,
            description="Fin de sesión",
            alert_text="Final de sesión.",
        )
        self.name = "Session End"
        self._fired = False

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if session_enable_flag(session, "enable_session_end_messages", True):
            return False
        if self._fired:
            return False

        lap = int(telemetry.get("lap_number", 0) or 0)
        if lap < 2:
            return False

        laps_left = float(telemetry.get("session_laps_left", 999.0))
        time_left = float(telemetry.get("session_time_left", 99999.0))
        session_over = bool(telemetry.get("session_over", False))

        ending = session_over or (0 < laps_left <= 1) or (0 < time_left <= 60)
        if not ending:
            return False

        pos = int(telemetry.get("standing_position", 0) or 0)
        best = float(telemetry.get("lap_time_best", 0.0) or 0.0)
        best_txt = f"{best:.3f}s" if best > 0 else "N/A"
        self.alert_text = f"Final de sesión — P{pos}, mejor vuelta {best_txt}. Resumen en camino."
        self._fired = True
        return True


class BrakeWearCriticalTrigger(BaseTrigger):
    """Trigger 3: Desgaste crítico de frenos (> 80% en alguna rueda)."""

    def __init__(self) -> None:
        super().__init__(
            Priority.CRITICAL,
            ContextTier.FAST,
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=20.0,
            description="Desgaste crítico de frenos",
            alert_text="Fallback desgaste frenos alto.",
            phrase_key="brake_wear_high",
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if session_enable_flag(session, "enable_brake_wear_messages", True):
            return False
        w_fl = telemetry.get("brake_wear_fl", 0.0)
        w_fr = telemetry.get("brake_wear_fr", 0.0)
        w_rl = telemetry.get("brake_wear_rl", 0.0)
        w_rr = telemetry.get("brake_wear_rr", 0.0)
        raw = any(w > 80.0 for w in [w_fl, w_fr, w_rl, w_rr])
        return self._fire_rising_edge(raw)


class TyreDegAccelTrigger(BaseTrigger):
    """Trigger 4: Degradación acelerada en neumáticos (> 25% de desgaste promedio)."""

    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.STANDARD,
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=30.0,
            description="Degradación de neumáticos acelerada",
            alert_text="Fallback desgaste neumáticos alto.",
            phrase_key="tyre_wear_high",
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if session_enable_flag(session, "enable_tyre_wear_messages", True):
            return False
        if not telemetry_on_track(telemetry):
            return False
        w_fl = telemetry.get("tyre_wear_fl", 0.0)
        w_fr = telemetry.get("tyre_wear_fr", 0.0)
        w_rl = telemetry.get("tyre_wear_rl", 0.0)
        w_rr = telemetry.get("tyre_wear_rr", 0.0)
        avg_wear = (w_fl + w_fr + w_rl + w_rr) / 4.0
        return avg_wear > 25.0


class HybridDeployMapTrigger(BaseTrigger):
    """Trigger 5: Batería baja (< 20%) y tendencia de descarga neta negativa."""

    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.STANDARD,
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=30.0,
            description="Estado SOC híbrido crítico",
            alert_text="Carga de batería híbrida baja. Optimiza mapeo para recarga.",
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if session_enable_flag(session, "enable_battery_messages", True):
            return False
        if not telemetry_on_track(telemetry):
            return False
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
            alert_text="Fallback probabilidad de lluvia.",
            phrase_key="rain_increasing",
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if not telemetry_on_track(telemetry):
            return False
        weather_list = session.get("weather_forecast", [])
        if not isinstance(weather_list, list) or not weather_list:
            return False
        # Evaluar los primeros nodos de previsión (ej: NODE_25, NODE_50)
        for slot in weather_list[:2]:
            if isinstance(slot, dict):
                rain_chance = lmu_scalar(slot.get("WNV_RAIN_CHANCE", 0.0))
                if rain_chance > 30.0:
                    return True
        return False


class PitWindowOpenedTrigger(BaseTrigger):
    """Trigger 7: Ventana de paradas en boxes abierta."""

    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.STANDARD,
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=30.0,
            description="Ventana de parada abierta",
            alert_text="Fallback ventana de parada abierta.",
            phrase_key="pit_window_opened",
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if session_enable_flag(session, "enable_pit_stop_messages", True):
            return False
        if not _legacy_on_track(telemetry):
            return False
        pit_window = strategy.get("pit_window") or {}
        raw = pit_window.get("pit_window_open", False) and not telemetry.get("in_pits", False)
        return self._fire_rising_edge(raw)


class PitWindowClosingTrigger(BaseTrigger):
    """Trigger 8: Ventana de paradas cerrándose (quedan <= 2 vueltas de ventana abierta)."""

    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.FAST,
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=15.0,
            description="Ventana de parada cerrándose",
            alert_text="Ventana de boxes a punto de cerrar. Parada obligatoria inminente.",
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if session_enable_flag(session, "enable_pit_stop_messages", True):
            return False
        if not _legacy_on_track(telemetry):
            return False
        pit_window = strategy.get("pit_window") or {}
        window_open = pit_window.get("pit_window_open", False)
        laps_remaining_in_window = pit_window.get("optimal_pit_lap", 0) - telemetry.get("lap_number", 0)
        raw = window_open and 0 <= laps_remaining_in_window <= 2 and not telemetry.get("in_pits", False)
        return self._fire_rising_edge(raw)


class CompetitorPittedTrigger(BaseTrigger):
    """Trigger 9: Un competidor directo (posición contigua) entra a boxes."""

    def __init__(self) -> None:
        super().__init__(
            Priority.MEDIUM,
            ContextTier.STANDARD,
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=15.0,
            description="Competidor directo en boxes",
            alert_text="Rival directo parado en boxes. Oportunidad de undercut/overcut.",
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if not telemetry_on_track(telemetry):
            return False
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
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=10.0,
            description="Brecha cerrada con rival",
            alert_text="Brecha menor a 1.5 segundos. Entrando en zona de batalla táctica.",
        )

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if session_enable_flag(session, "enable_gap_messages", True):
            return False
        if not _legacy_on_track(telemetry):
            return False
        gap_ahead, gap_behind = resolve_gaps(telemetry)
        raw = gap_ahead < 1.5 or gap_behind < 1.5
        return self._fire_rising_edge(raw)


class PhaseChangedTrigger(BaseTrigger):
    """Trigger 11: Cambio en la fase de carrera (ej: paso de clasificación a carrera, o bandera roja)."""

    def __init__(self) -> None:
        super().__init__(
            Priority.HIGH,
            ContextTier.FAST,
            TriggerAction.LLM_REQUIRED,
            min_interval=5.0,
            description="Cambio de fase de carrera",
            alert_text="Fase de carrera actualizada. Re-evaluando estrategia.",
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
            alert_text="Procesando consulta directa por radio...",
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
            TriggerAction.DETERMINISTIC_ONLY,
            min_interval=30.0,
            description="Temperatura excesiva de neumáticos",
            alert_text="¡ATENCIÓN! Temperatura de neumáticos elevada.",
        )
        self.name = "Tires Thermal Overheating"

    def condition(self, telemetry: dict, strategy: dict, session: dict) -> bool:
        if session_enable_flag(session, "enable_tyre_temp_messages", True):
            return False
        if not telemetry_on_track(telemetry):
            return False
        t_fl = telemetry.get("tyre_temp_fl", 0.0)
        t_fr = telemetry.get("tyre_temp_fr", 0.0)
        t_rl = telemetry.get("tyre_temp_rl", 0.0)
        t_rr = telemetry.get("tyre_temp_rr", 0.0)
        return any(t > 105.0 for t in [t_fl, t_fr, t_rl, t_rr])


def get_all_triggers() -> list[BaseTrigger]:
    """Triggers legacy que aún evalúa evaluate_cycle (solo LLM + utilitarios de test)."""
    return [
        FlagsMonitorTrigger(),
        TiresThermalOverheatingTrigger(),
        WeatherChangeTrigger(),
        PhaseChangedTrigger(),
        PilotQuestionTrigger(),
    ]
