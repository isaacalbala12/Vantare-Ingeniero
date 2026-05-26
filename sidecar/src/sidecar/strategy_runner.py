import logging
import math
from typing import Optional

from shared_telemetry import TelemetryReader
from shared_telemetry.sync import TelemetrySync
from shared_strategy import compute_strategy
from shared_strategy.models import (
    TelemetryFrame,
    StrategyState,
    TrackConfig,
    StrategyAdvice,
    CompetitorTelemetry,
)


logger = logging.getLogger("vantare.sidecar.strategy")


def safe_float(val):
    try:
        f = float(val)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def safe_str(val):
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace").rstrip("\0 ").rstrip()
    return str(val) if val is not None else ""


class StrategyRunner:
    """Strategy computation runner for sidecar (no backend Linux dependencies)."""

    def __init__(self, reader: TelemetryReader) -> None:
        self.reader = reader
        self.sync = TelemetrySync()
        self.state = StrategyState()
        self.track = TrackConfig(track_length=7004.0)
        self.latest_advice: Optional[StrategyAdvice] = None
        self.latest_frame: Optional[TelemetryFrame] = None
        self._simulated_fuel = 100.0
        self._last_lap = 0
        self._lap_fuel_start = 100.0
        self._prev_battery_charge = 100.0
        self._lap_battery_drain = 0.0
        self._lap_battery_regen = 0.0

    def process_cycle(self) -> None:
        """Main processing cycle - replicates _process_cycle() logic without backend deps."""
        race_state = self.reader.get_state()
        if race_state is None or race_state.player is None:
            return

        data = self.reader.shmm.data
        if data is None:
            return

        scor_idx, tele_idx, player_scor, player_tele = self.sync.sync_player_data(data)
        if player_scor is None:
            return

        # Session type mapping
        session_type_map = {0: "practice", 1: "practice", 2: "qualifying"}
        session_type = session_type_map.get(race_state.session.session_type, "race")

        scoring_info = data.scoring.scoringInfo

        # Auto-calibrate track length
        track_dist = safe_float(scoring_info.mLapDist)
        if track_dist > 10.0:
            self.track.track_length = track_dist

        # Session info
        max_laps = int(scoring_info.mMaxLaps) if scoring_info.mMaxLaps > 0 else 999
        current_lap = race_state.player.current_lap
        session_laps_left = max(0, max_laps - current_lap)
        session_time_left = race_state.session.time_remaining

        # Game phase flags
        game_phase = scoring_info.mGamePhase
        safety_car_active = game_phase == 6
        full_course_yellow_active = game_phase == 6
        has_sector_yellow = any(scoring_info.mSectorFlag[i] != 0 for i in range(3))
        yellow_flag_active = game_phase == 6 or has_sector_yellow

        # Player telemetry
        if player_tele is not None:
            fuel_in_tank = safe_float(player_tele.mFuel)
            fuel_capacity = safe_float(player_tele.mFuelCapacity)
            is_invalid_lap = bool(player_tele.mLapInvalidated)
            pit_limiter_active = bool(player_tele.mSpeedLimiterActive)
            speed = math.sqrt(
                safe_float(player_tele.mLocalVel.x) ** 2
                + safe_float(player_tele.mLocalVel.y) ** 2
                + safe_float(player_tele.mLocalVel.z) ** 2
            )
            battery_charge = safe_float(player_tele.mStateOfCharge)
            motor_state_val = player_tele.mElectricBoostMotorState
            if motor_state_val == 2:
                motor_state = 2  # Drain
            elif motor_state_val == 3:
                motor_state = 3  # Regen
            else:
                motor_state = 1  # Idle
        else:
            fuel_in_tank = 0.0
            fuel_capacity = 100.0
            is_invalid_lap = False
            pit_limiter_active = False
            speed = 0.0
            battery_charge = 100.0
            motor_state = 1

        # Lap accumulators
        if self._last_lap == 0 or current_lap > self._last_lap:
            self._lap_fuel_start = fuel_in_tank
            self._lap_battery_drain = 0.0
            self._lap_battery_regen = 0.0
            self._last_lap = current_lap

        fuel_used_lap_raw = max(0.0, self._lap_fuel_start - fuel_in_tank)
        charge_diff = battery_charge - self._prev_battery_charge
        if charge_diff < 0:
            self._lap_battery_drain += abs(charge_diff)
        elif charge_diff > 0:
            self._lap_battery_regen += charge_diff
        self._prev_battery_charge = battery_charge

        # Tyre wear (ONLINE mode - sidecar always uses real shared memory)
        tyre_wear_fl = race_state.tyres.wear[0] * 100.0
        tyre_wear_fr = race_state.tyres.wear[1] * 100.0
        tyre_wear_rl = race_state.tyres.wear[2] * 100.0
        tyre_wear_rr = race_state.tyres.wear[3] * 100.0

        # Tyre temperatures
        tyre_temp_fl = race_state.tyres.carcass_temperatures[0]
        tyre_temp_fr = race_state.tyres.carcass_temperatures[1]
        tyre_temp_rl = race_state.tyres.carcass_temperatures[2]
        tyre_temp_rr = race_state.tyres.carcass_temperatures[3]

        # Brake wear - all 0.0 (no REST API access)
        brake_wear_fl = 0.0
        brake_wear_fr = 0.0
        brake_wear_rl = 0.0
        brake_wear_rr = 0.0

        # Competitor syncing
        competitors_list: list[CompetitorTelemetry] = []
        veh_total = min(int(scoring_info.mNumVehicles), len(data.scoring.vehScoringInfo))

        for idx in range(veh_total):
            veh_info = data.scoring.vehScoringInfo[idx]
            if veh_info.mIsPlayer or veh_info.mID <= 0:
                continue

            tele_index = self.sync._tele_indexes.get(veh_info.mID, -1)
            opp_tele = data.telemetry.telemetryData[tele_index] if tele_index >= 0 else None

            if opp_tele is not None:
                opp_speed = math.sqrt(
                    safe_float(opp_tele.mLocalVel.x) ** 2
                    + safe_float(opp_tele.mLocalVel.y) ** 2
                    + safe_float(opp_tele.mLocalVel.z) ** 2
                )
            else:
                opp_speed = 0.0

            fuel_fraction = veh_info.mFuelFraction / 255.0
            pit_requested = veh_info.mPitState == 1

            competitor = CompetitorTelemetry(
                id=veh_info.mID,
                name=safe_str(veh_info.mDriverName),
                position=int(veh_info.mPlace),
                speed=opp_speed,
                fuel_fraction=fuel_fraction,
                in_pits=pit_requested,
                pit_requested=pit_requested,
            )
            competitors_list.append(competitor)

        # Determine player states
        player = race_state.player
        in_pits = bool(player.in_pits)
        throttle = race_state.inputs.throttle
        in_garage = bool(player.in_pits and throttle < 0.01)

        # Assemble TelemetryFrame
        frame = TelemetryFrame(
            session_type=session_type,
            session_time_left=session_time_left,
            session_laps_left=session_laps_left,
            lap_number=current_lap,
            lap_distance=player.lap_distance,
            lap_time_best=race_state.lap_times.best,
            lap_time_previous=race_state.lap_times.previous,
            is_invalid_lap=is_invalid_lap,
            in_garage=in_garage,
            in_pits=in_pits,
            pit_limiter_active=pit_limiter_active,
            yellow_flag_active=yellow_flag_active,
            safety_car_active=safety_car_active,
            full_course_yellow_active=full_course_yellow_active,
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
            throttle=throttle,
            brake=race_state.inputs.brake,
            pos_x=player.position_xyz.x,
            pos_y=player.position_xyz.y,
            pos_z=player.position_xyz.z,
            competitors=competitors_list,
        )

        # Compute strategy
        advice, new_state = compute_strategy(frame, self.state, self.track)
        self.state = new_state
        self.latest_advice = advice
        self.latest_frame = frame
