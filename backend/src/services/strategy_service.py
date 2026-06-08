import asyncio
import logging
import threading
import time
from typing import Optional

from shared_telemetry import TelemetryReader, RaceState
from shared_telemetry.sync import TelemetrySync
from shared_telemetry.session_kind import session_kind_from_lmu_int
from shared_strategy import compute_strategy, TelemetryFrame, StrategyState, TrackConfig, StrategyAdvice
from shared_strategy.telemetry_frame_builder import (
    FrameBuildContext,
    StrategyFrameState,
    build_telemetry_frame_from_reader_state,
    safe_float,
    safe_str,
)

from src.config import settings
from src.services.lmu_api import get_additional_data

# Evento global para sincronización de arranque
strategy_ready = asyncio.Event()

logger = logging.getLogger("vantare.strategy_service")


class StrategyService:
    """Servicio que orquestador el motor de estrategia (shared-strategy).

    Recibe telemetría desde TelemetryReader, procesa los campos requeridos
    (resolviendo la brecha de combustible mediante acceso directo a ctypes)
    y ejecuta el motor determinista de estrategia cada 2 segundos.
    """

    def __init__(self, reader: TelemetryReader) -> None:
        self.reader = reader
        self.sync = TelemetrySync()
        
        # Estado persistente del motor de estrategia
        self.state = StrategyState()
        
        # Configuración por defecto del circuito (se autocalibrará en tiempo real)
        self.track = TrackConfig(track_length=7004.0)  # Valor inicial por defecto (Spa)
        
        # Último consejo estratégico calculado
        self.latest_advice: Optional[StrategyAdvice] = None
        self.latest_frame: Optional[TelemetryFrame] = None

        self._frame_state = StrategyFrameState()
        self._frame_lock = threading.Lock()
        self._cached_brake_wear: Optional[dict[str, float]] = None
        self._state_detector = None
        self._latest_events: list[dict] = []
        
        # Tarea asíncrona del bucle en background
        self._loop_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Arranca el bucle asíncrono en background desde el lifespan de FastAPI."""
        if self._loop_task is not None:
            return
        self._loop_task = asyncio.create_task(self._run_loop())
        logger.info("StrategyService loop started")

    async def stop(self) -> None:
        """Detiene el bucle asíncrono."""
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
            logger.info("StrategyService loop stopped")

    def get_latest_advice(self) -> Optional[StrategyAdvice]:
        return self.latest_advice

    def get_latest_events(self) -> list[dict]:
        return list(self._latest_events)

    def _fetch_brake_wear_from_rest(self) -> dict[str, float]:
        brake_wear = {"fl": 0.0, "fr": 0.0, "rl": 0.0, "rr": 0.0}
        try:
            brakes_api = get_additional_data("brakes")
            if isinstance(brakes_api, dict):
                if "fl" in brakes_api:
                    def _extract_wear(data):
                        w = data.get("wear", 0.0) if isinstance(data, dict) else float(data)
                        return w * 100.0 if w <= 1.0 else w

                    brake_wear["fl"] = _extract_wear(brakes_api.get("fl", {}))
                    brake_wear["fr"] = _extract_wear(brakes_api.get("fr", {}))
                    brake_wear["rl"] = _extract_wear(brakes_api.get("rl", {}))
                    brake_wear["rr"] = _extract_wear(brakes_api.get("rr", {}))
                elif "wear" in brakes_api:
                    wear_list = brakes_api["wear"]
                    if isinstance(wear_list, list) and len(wear_list) >= 4:
                        def _scale(w):
                            return w * 100.0 if w <= 1.0 else w
                        brake_wear["fl"] = _scale(wear_list[0])
                        brake_wear["fr"] = _scale(wear_list[1])
                        brake_wear["rl"] = _scale(wear_list[2])
                        brake_wear["rr"] = _scale(wear_list[3])
        except Exception as e:
            logger.debug("Failed to extract brake wear: %s", e)
        return brake_wear

    def _make_frame_context(self, race_state: RaceState, *, include_rest: bool) -> FrameBuildContext:
        shmm_data = None
        if not self.reader.offline and self.reader.shmm and self.reader.shmm.data:
            shmm_data = self.reader.shmm.data

        if include_rest:
            self._cached_brake_wear = self._fetch_brake_wear_from_rest()

        return FrameBuildContext(
            track=self.track,
            sync=self.sync,
            reader_offline=self.reader.offline,
            shmm_data=shmm_data,
            cached_brake_wear=self._cached_brake_wear,
        )

    def _build_frame(self, race_state: RaceState, *, include_rest: bool) -> TelemetryFrame:
        ctx = self._make_frame_context(race_state, include_rest=include_rest)
        return build_telemetry_frame_from_reader_state(
            race_state=race_state,
            ctx=ctx,
            frame_state=self._frame_state,
        )

    def snapshot_frame(self) -> dict | None:
        """20 Hz path: shared memory → TelemetryFrame dict. No REST, no compute_strategy."""
        race_state = self.reader.get_state()
        if race_state is None or race_state.player is None:
            return None
        with self._frame_lock:
            frame = self._build_frame(race_state, include_rest=False)
            self.latest_frame = frame
            return frame.model_dump(mode="json")

    def reset_stint_on_driver_swap(self) -> None:
        """Resetea acumuladores de stint tras cambio de piloto (endurance)."""
        if self.latest_frame is not None:
            self._frame_state.lap_fuel_start = self.latest_frame.fuel_in_tank
        self._frame_state.lap_battery_drain = 0.0
        self._frame_state.lap_battery_regen = 0.0

        new_state = self.state.model_copy(deep=True)
        new_state.fuel.consumption_history = []
        new_state.fuel.delta_array_raw = []
        new_state.fuel.delta_array_last = []
        new_state.fuel.validating = True
        self.state = new_state
        logger.info("Stint reseteado por cambio de piloto")

    async def wait_until_ready(self, timeout: float = 10.0) -> bool:
        """Espera hasta que el primer ciclo de estrategia se complete."""
        try:
            await asyncio.wait_for(strategy_ready.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning("StrategyService no estuvo listo en %fs", timeout)
            return False

    def get_race_summary(self) -> dict:
        """Genera un resumen estructurado del estado actual de la carrera para inyectar en el LLM."""
        race_state = self.reader.get_state()
        if not race_state or not race_state.player:
            return {"status": "No en pista o telemetría inactiva"}

        player = race_state.player
        session = race_state.session
        advice = self.latest_advice
        frame = self.latest_frame

        tyres = race_state.tyres
        wear_fl = (1.0 - tyres.wear[0]) * 100.0 if self.reader.offline else tyres.wear[0] * 100.0
        wear_fr = (1.0 - tyres.wear[1]) * 100.0 if self.reader.offline else tyres.wear[1] * 100.0
        wear_rl = (1.0 - tyres.wear[2]) * 100.0 if self.reader.offline else tyres.wear[2] * 100.0
        wear_rr = (1.0 - tyres.wear[3]) * 100.0 if self.reader.offline else tyres.wear[3] * 100.0

        summary = {
            "session_type": session_kind_from_lmu_int(session.session_type),
            "lap_number": player.current_lap,
            "position": player.place,
            "fuel_in_tank": frame.fuel_in_tank if frame else 0.0,
            "fuel_needed_to_finish": advice.fuel.fuel_needed_to_finish if advice and advice.fuel else 0.0,
            "laps_remaining_estimate": advice.fuel.estimated_laps_remaining if advice and advice.fuel else 0.0,
            "pit_windows": {
                "pit_strategy": f"Optimal stop on lap {advice.pit_window.optimal_pit_lap}" if advice and advice.pit_window else "unknown",
                "recommended_pit_lap": advice.pit_window.optimal_pit_lap if advice and advice.pit_window else 0
            },
            "tyres": {
                "wear_fl": round(wear_fl, 1),
                "wear_fr": round(wear_fr, 1),
                "wear_rl": round(wear_rl, 1),
                "wear_rr": round(wear_rr, 1),
                "temp_fl": round(tyres.carcass_temperatures[0], 1),
                "temp_fr": round(tyres.carcass_temperatures[1], 1),
                "temp_rl": round(tyres.carcass_temperatures[2], 1),
                "temp_rr": round(tyres.carcass_temperatures[3], 1),
            },
            "flags": {
                "safety_car": frame.safety_car_active if frame else False,
                "yellow_flag": frame.yellow_flag_active if frame else False,
                "full_course_yellow": frame.full_course_yellow_active if frame else False
            }
        }
        return summary

    async def _run_loop(self) -> None:
        """Bucle asíncrono que corre cada STRATEGY_POLL_RATE segundos."""
        try:
            while True:
                start_time = time.monotonic()
                try:
                    self._process_cycle()
                except Exception as e:
                    logger.error(f"Error in strategy calculation cycle: {e}", exc_info=True)

                # Calcular sleep dinámico para mantener la frecuencia exacta
                elapsed = time.monotonic() - start_time
                sleep_time = max(0.1, settings.STRATEGY_POLL_RATE - elapsed)
                await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            logger.debug("StrategyService run loop cancelled")

    def _process_cycle(self) -> None:
        """Procesa un ciclo del motor estratégico (@ 2 Hz, incluye REST brakes)."""
        race_state = self.reader.get_state()
        if race_state is None or race_state.player is None:
            return

        with self._frame_lock:
            frame = self._build_frame(race_state, include_rest=True)
            advice, new_state = compute_strategy(frame, self.state, self.track)
            self.state = new_state
            self.latest_advice = advice
            self.latest_frame = frame

            if self._state_detector is None:
                from src.services.state_change_detector import StateChangeDetector
                self._state_detector = StateChangeDetector()
            self._latest_events = self._state_detector.detect(frame)

        if not strategy_ready.is_set():
            strategy_ready.set()

        logger.debug(
            "Strategy compute successful: laps left=%s, fuel needed=%.2fL",
            frame.session_laps_left,
            advice.fuel.fuel_needed_to_finish if advice.fuel else 0.0,
        )
