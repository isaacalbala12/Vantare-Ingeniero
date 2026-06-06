import asyncio
import logging
import math
import time
from typing import Optional

from shared_telemetry import TelemetryReader, RaceState
from shared_telemetry.sync import TelemetrySync
from shared_strategy import compute_strategy, TelemetryFrame, StrategyState, TrackConfig, StrategyAdvice
from shared_strategy.models import CompetitorTelemetry

from src.config import settings
from src.services.lmu_api import get_additional_data

# Evento global para sincronización de arranque
strategy_ready = asyncio.Event()

logger = logging.getLogger("vantare.strategy_service")


def safe_float(val) -> float:
    """Convierte un valor a float de forma segura, previniendo inf y nan."""
    try:
        f = float(val)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def safe_str(val) -> str:
    """Convierte bytes de ctypes a string de Python de forma segura."""
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace").rstrip("\0 ").rstrip()
    return str(val) if val is not None else ""


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
        
        # Tarea asíncrona del bucle en background
        self._loop_task: Optional[asyncio.Task] = None
        
        # Estados auxiliares para acumuladores de vuelta
        self._simulated_fuel = 100.0
        self._last_lap = 0
        self._lap_fuel_start = 100.0
        self._prev_battery_charge = 100.0
        self._lap_battery_drain = 0.0
        self._lap_battery_regen = 0.0

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
        """Obtiene el último consejo estratégico calculado."""
        return self.latest_advice

    def reset_stint_on_driver_swap(self) -> None:
        """Resetea acumuladores de stint tras cambio de piloto (endurance)."""
        if self.latest_frame is not None:
            self._lap_fuel_start = self.latest_frame.fuel_in_tank
        self._lap_battery_drain = 0.0
        self._lap_battery_regen = 0.0

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
            "session_type": "practice" if session.session_type in (0, 1) else "qualifying" if session.session_type == 2 else "race",
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
        """Procesa un ciclo del motor estratégico."""
        race_state = self.reader.get_state()
        if race_state is None or race_state.player is None:
            return

        player = race_state.player
        session = race_state.session
        
        # 1. Determinar tipo de sesión en string
        session_type_int = session.session_type
        if session_type_int in (0, 1):
            session_type_str = "practice"
        elif session_type_int == 2:
            session_type_str = "qualifying"
        else:
            session_type_str = "race"

        # 2. Extraer datos y resolver brecha de combustible (ctypes si online, simulado si offline)
        fuel_in_tank = 100.0
        fuel_capacity = 100.0
        is_invalid_lap = False
        pit_limiter_active = False
        speed = 0.0
        vel_x = vel_y = vel_z = 0.0
        motor_state = 1
        battery_charge = 100.0
        session_laps_left = 999.0
        safety_car_active = False
        full_course_yellow_active = False
        yellow_flag_active = False
        blue_flag_active = False
        session_stopped = False
        session_over = False
        num_penalties = 0
        driver_name = safe_str(player.driver_name)

        if not self.reader.offline and self.reader.shmm and self.reader.shmm.data:
            data = self.reader.shmm.data
            scor_idx, tele_idx, player_scor, player_tele = self.sync.sync_player_data(data)
            
            # Autocalibrar longitud de pista real
            scoring_info = data.scoring.scoringInfo
            if scoring_info.mLapDist > 10.0:
                self.track.track_length = scoring_info.mLapDist

            # Laps left
            max_laps = scoring_info.mMaxLaps
            if max_laps > 0:
                session_laps_left = max(0.0, float(max_laps - player.current_lap))

            # Banderas de la sesión
            game_phase = int(scoring_info.mGamePhase)
            safety_car_active = (game_phase == 6)
            full_course_yellow_active = (game_phase == 6)
            session_stopped = (game_phase == 7)
            session_over = (game_phase == 8)
            has_sector_yellow = any(scoring_info.mSectorFlag[i] != 0 for i in range(3))
            yellow_flag_active = (game_phase == 6 or has_sector_yellow)

            if player_scor is not None:
                num_penalties = max(0, int(player_scor.mNumPenalties))
                blue_flag_active = (int(player_scor.mFlag) == 6)

            if player_tele is not None:
                fuel_in_tank = safe_float(player_tele.mFuel)
                fuel_capacity = safe_float(player_tele.mFuelCapacity)
                is_invalid_lap = bool(player_tele.mLapInvalidated)
                pit_limiter_active = bool(player_tele.mSpeedLimiterActive)
                vel_x = safe_float(player_tele.mLocalVel.x)
                vel_y = safe_float(player_tele.mLocalVel.y)
                vel_z = safe_float(player_tele.mLocalVel.z)
                
                # Velocidad real en m/s desde vector de velocidad local
                speed = math.sqrt(vel_x ** 2 + vel_y ** 2 + vel_z ** 2)
                
                # Mapear boost motor state
                # LMU: 0=unavailable, 1=inactive, 2=propulsion (drain), 3=regeneration (regen)
                # shared-strategy: 1=Idle, 2=Drain, 3=Regen
                boost_state = int(player_tele.mElectricBoostMotorState)
                if boost_state == 2:
                    motor_state = 2
                elif boost_state == 3:
                    motor_state = 3
                else:
                    motor_state = 1
                
                battery_charge = safe_float(player_tele.mStateOfCharge)
            else:
                # Fallback seguro si no hay telemetría del jugador
                fuel_in_tank = 100.0
                fuel_capacity = 100.0
                is_invalid_lap = False
                pit_limiter_active = False
                speed = 0.0
                vel_x = vel_y = vel_z = 0.0
                motor_state = 1
                battery_charge = 100.0
        else:
            vel_x = vel_y = vel_z = 0.0
            # Modo Offline / Simulado
            # Laps left
            if session.time_remaining > 0:
                session_laps_left = -1.0  # Sesión por tiempo
            
            # Decremento de combustible simulado
            current_lap = player.current_lap
            if self._last_lap == 0:
                self._simulated_fuel = 100.0
                self._last_lap = current_lap
            elif current_lap > self._last_lap:
                laps_diff = current_lap - self._last_lap
                self._simulated_fuel = max(0.0, self._simulated_fuel - (3.5 * laps_diff))
                self._last_lap = current_lap

            fuel_in_tank = self._simulated_fuel
            fuel_capacity = 100.0
            is_invalid_lap = False
            pit_limiter_active = False
            speed = 50.0  # m/s simulados (~180 km/h)
            motor_state = 1
            battery_charge = 85.0

        # 3. Calcular acumulados de la vuelta (fuel_used_lap_raw, battery_drain, battery_regen)
        current_lap = player.current_lap
        if self._last_lap == 0 or current_lap > self._last_lap:
            self._lap_fuel_start = fuel_in_tank
            self._lap_battery_drain = 0.0
            self._lap_battery_regen = 0.0
            self._last_lap = current_lap

        # Consumo de combustible en la vuelta actual
        fuel_used_lap_raw = max(0.0, self._lap_fuel_start - fuel_in_tank)

        # Cambios de batería (porcentaje 0-100)
        charge_diff = battery_charge - self._prev_battery_charge
        if charge_diff < 0:
            self._lap_battery_drain += abs(charge_diff)
        elif charge_diff > 0:
            self._lap_battery_regen += charge_diff
        self._prev_battery_charge = battery_charge

        # 4. Mapear neumáticos:wear (escalar wear de 0.0-1.0 a 0.0-100.0)
        wear_fl_raw = race_state.tyres.wear[0]
        wear_fr_raw = race_state.tyres.wear[1]
        wear_rl_raw = race_state.tyres.wear[2]
        wear_rr_raw = race_state.tyres.wear[3]

        if self.reader.offline:
            # En offline wear va de 1.0 (nuevo) a 0.0 (gastado)
            tyre_wear_fl = (1.0 - wear_fl_raw) * 100.0
            tyre_wear_fr = (1.0 - wear_fr_raw) * 100.0
            tyre_wear_rl = (1.0 - wear_rl_raw) * 100.0
            tyre_wear_rr = (1.0 - wear_rr_raw) * 100.0
        else:
            # En online wear va de 0.0 (nuevo) a 1.0 (gastado)
            tyre_wear_fl = wear_fl_raw * 100.0
            tyre_wear_fr = wear_fr_raw * 100.0
            tyre_wear_rl = wear_rl_raw * 100.0
            tyre_wear_rr = wear_rr_raw * 100.0

        # Carcass temperatures
        tyre_temp_fl = race_state.tyres.carcass_temperatures[0]
        tyre_temp_fr = race_state.tyres.carcass_temperatures[1]
        tyre_temp_rl = race_state.tyres.carcass_temperatures[2]
        tyre_temp_rr = race_state.tyres.carcass_temperatures[3]

        # 5. Obtener desgaste de frenos desde REST API
        brake_wear_fl = brake_wear_fr = brake_wear_rl = brake_wear_rr = 0.0
        try:
            brakes_api = get_additional_data("brakes")
            if isinstance(brakes_api, dict):
                if "fl" in brakes_api:
                    fl_data = brakes_api.get("fl", {})
                    fr_data = brakes_api.get("fr", {})
                    rl_data = brakes_api.get("rl", {})
                    rr_data = brakes_api.get("rr", {})
                    
                    def _extract_wear(data):
                        w = data.get("wear", 0.0) if isinstance(data, dict) else float(data)
                        # Si está en fracción 0.0-1.0 lo multiplicamos por 100
                        return w * 100.0 if w <= 1.0 else w

                    brake_wear_fl = _extract_wear(fl_data)
                    brake_wear_fr = _extract_wear(fr_data)
                    brake_wear_rl = _extract_wear(rl_data)
                    brake_wear_rr = _extract_wear(rr_data)
                elif "wear" in brakes_api:
                    wear_list = brakes_api["wear"]
                    if isinstance(wear_list, list) and len(wear_list) >= 4:
                        def _scale(w):
                            return w * 100.0 if w <= 1.0 else w
                        brake_wear_fl = _scale(wear_list[0])
                        brake_wear_fr = _scale(wear_list[1])
                        brake_wear_rl = _scale(wear_list[2])
                        brake_wear_rr = _scale(wear_list[3])
        except Exception as e:
            logger.debug(f"Failed to extract brake wear: {e}")

        # 6. Sincronizar competidores
        competitors_list = []
        if not self.reader.offline and self.reader.shmm and self.reader.shmm.data:
            data = self.reader.shmm.data
            scoring_info = data.scoring.scoringInfo
            veh_total = min(int(scoring_info.mNumVehicles), len(data.scoring.vehScoringInfo))

            for idx in range(veh_total):
                veh_info = data.scoring.vehScoringInfo[idx]
                if veh_info.mID > 0 and not veh_info.mIsPlayer:
                    # Buscar velocidad en telemetría
                    opp_tele_idx = self.sync._tele_indexes.get(veh_info.mID, -1)
                    opp_speed = 0.0
                    if opp_tele_idx != -1 and opp_tele_idx < len(data.telemetry.telemInfo):
                        opp_tele = data.telemetry.telemInfo[opp_tele_idx]
                        opp_speed = math.sqrt(
                            safe_float(opp_tele.mLocalVel.x) ** 2 +
                            safe_float(opp_tele.mLocalVel.y) ** 2 +
                            safe_float(opp_tele.mLocalVel.z) ** 2
                        )
                    
                    fuel_fraction = veh_info.mFuelFraction / 255.0
                    pit_requested = (veh_info.mPitState == 1)

                    comp = CompetitorTelemetry(
                        driver_index=int(veh_info.mID),
                        driver_name=safe_str(veh_info.mDriverName),
                        driver_class=safe_str(veh_info.mVehicleClass),
                        standing_position=int(veh_info.mPlace),
                        class_position=int(veh_info.mPlace),  # Fallback a standing position
                        lap_number=int(veh_info.mTotalLaps + 1),
                        lap_distance=safe_float(veh_info.mLapDist),
                        lap_time_best=safe_float(veh_info.mBestLapTime),
                        lap_time_previous=safe_float(veh_info.mLastLapTime),
                        in_pits=bool(veh_info.mInPits),
                        pit_requested=pit_requested,
                        estimated_time_into_lap=safe_float(veh_info.mTimeIntoLap),
                        speed=opp_speed,
                        fuel_capacity_fraction=fuel_fraction,
                        pos_x=safe_float(veh_info.mPos.x),
                        pos_y=safe_float(veh_info.mPos.y),
                        pos_z=safe_float(veh_info.mPos.z),
                    )
                    competitors_list.append(comp)
        else:
            # Modo Offline: Mapear rivales desde RaceState
            for opp_id, opp_data in race_state.opponents.items():
                comp = CompetitorTelemetry(
                    driver_index=opp_id,
                    driver_name=opp_data.driver_name,
                    driver_class=opp_data.class_name,
                    standing_position=opp_data.place,
                    class_position=opp_data.place,
                    lap_number=opp_data.current_lap,
                    lap_distance=opp_data.lap_distance,
                    lap_time_best=opp_data.best_laptime,
                    lap_time_previous=opp_data.last_laptime,
                    in_pits=opp_data.in_pits,
                    pit_requested=False,
                    estimated_time_into_lap=0.0,
                    speed=opp_data.lap_distance / 90.0,
                    fuel_capacity_fraction=0.8,
                    pos_x=opp_data.position_xyz[0],
                    pos_y=opp_data.position_xyz[1],
                    pos_z=opp_data.position_xyz[2],
                )
                competitors_list.append(comp)

        # 7. Ensamblar TelemetryFrame final
        frame = TelemetryFrame(
            session_type=session_type_str,
            session_time_left=session.time_remaining,
            session_laps_left=session_laps_left,
            lap_number=player.current_lap,
            lap_distance=player.lap_distance,
            lap_time_best=player.best_laptime,
            lap_time_previous=player.last_laptime,
            is_invalid_lap=is_invalid_lap,
            in_garage=bool(race_state.player.in_pits and race_state.inputs.throttle < 0.01),  # Inferencia simple
            in_pits=player.in_pits,
            pit_limiter_active=pit_limiter_active,
            
            yellow_flag_active=yellow_flag_active,
            safety_car_active=safety_car_active,
            full_course_yellow_active=full_course_yellow_active,
            blue_flag_active=blue_flag_active,
            session_stopped=session_stopped,
            session_over=session_over,
            driver_name=driver_name,
            num_penalties=num_penalties,

            fuel_in_tank=fuel_in_tank,
            fuel_capacity=fuel_capacity,
            fuel_used_lap_raw=fuel_used_lap_raw,
            battery_charge=battery_charge,
            battery_drain=self._lap_battery_drain,
            battery_regen=self._lap_battery_regen,
            motor_state=motor_state,

            tyre_wear_fl=tyre_wear_fl,
            tyre_wear_fr=tyre_wear_fr,
            tyre_wear_rl=tyre_wear_rl,
            tyre_wear_rr=tyre_wear_rr,
            tyre_temp_fl=tyre_temp_fl,
            tyre_temp_fr=tyre_temp_fr,
            tyre_temp_rl=tyre_temp_rl,
            tyre_temp_rr=tyre_temp_rr,

            brake_wear_fl=brake_wear_fl,
            brake_wear_fr=brake_wear_fr,
            brake_wear_rl=brake_wear_rl,
            brake_wear_rr=brake_wear_rr,

            speed=speed,
            throttle=race_state.inputs.throttle,
            brake=race_state.inputs.brake,
            pos_x=player.position_xyz[0],
            pos_y=player.position_xyz[1],
            pos_z=player.position_xyz[2],
            vel_x=vel_x,
            vel_y=vel_y,
            vel_z=vel_z,
            player_class=player.class_name,
            vehicle_name=player.vehicle_name,
            standing_position=int(player.place),
            competitors=competitors_list
        )

        # 8. Computar estrategia mediante shared-strategy
        advice, new_state = compute_strategy(frame, self.state, self.track)
        
        # 9. Guardar estado, consejo y frame para consulta asíncrona
        self.state = new_state
        self.latest_advice = advice
        self.latest_frame = frame

        # Señalizar que el primer ciclo se completó
        if not strategy_ready.is_set():
            strategy_ready.set()

        logger.debug(f"Strategy compute successful: laps left={session_laps_left}, fuel needed={advice.fuel.fuel_needed_to_finish:.2f}L")
