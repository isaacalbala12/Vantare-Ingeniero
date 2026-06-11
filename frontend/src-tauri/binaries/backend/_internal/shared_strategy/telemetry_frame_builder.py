"""Shared TelemetryFrame assembly for backend StrategyService and legacy sidecar."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from shared_strategy.models import CompetitorTelemetry, TelemetryFrame, TrackConfig
from shared_telemetry.lmu_damage import damage_fields_from_player_telemetry
from shared_telemetry.session_kind import session_kind_from_lmu_int


def safe_float(val) -> float:
    try:
        f = float(val)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def safe_str(val) -> str:
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace").rstrip("\0 ").rstrip()
    return str(val) if val is not None else ""


@dataclass
class StrategyFrameState:
    """Mutable lap/sim state owned by StrategyService / StrategyRunner."""

    simulated_fuel: float = 100.0
    last_lap: int = 0
    lap_fuel_start: float = 100.0
    lap_battery_drain: float = 0.0
    lap_battery_regen: float = 0.0
    prev_battery_charge: float = 100.0


@dataclass
class FrameBuildContext:
    track: TrackConfig
    sync: Any
    reader_offline: bool
    shmm_data: Any = None
    cached_brake_wear: Optional[dict[str, float]] = None


def _brake_wear_from_cache(cached: Optional[dict[str, float]]) -> tuple[float, float, float, float]:
    if not cached:
        return 0.0, 0.0, 0.0, 0.0
    return (
        float(cached.get("fl", 0.0)),
        float(cached.get("fr", 0.0)),
        float(cached.get("rl", 0.0)),
        float(cached.get("rr", 0.0)),
    )


def build_telemetry_frame_from_reader_state(
    *,
    race_state,
    ctx: FrameBuildContext,
    frame_state: StrategyFrameState,
) -> TelemetryFrame:
    """Build a TelemetryFrame from RaceState + shared memory (single source of truth)."""
    player = race_state.player
    session = race_state.session
    session_type_int = session.session_type
    session_type_str = session_kind_from_lmu_int(session_type_int)

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
    local_yellow_active = False
    blue_flag_active = False
    session_stopped = False
    session_over = False
    num_penalties = 0
    game_phase = 5
    sector_flags: list[int] = []
    driver_name = safe_str(player.driver_name)
    time_gap_car_ahead = 0.0
    time_gap_car_behind = 0.0
    time_gap_place_ahead = 0.0
    time_gap_place_behind = 0.0
    ori_fwd_x = 0.0
    ori_fwd_z = 0.0
    path_lateral = 0.0
    damage_fields = damage_fields_from_player_telemetry(None)
    rainfall = 0.0
    yellow_flag_state = 0
    local_accel_x = 0.0
    local_accel_y = 0.0
    local_accel_z = 0.0
    tyre_flat = [False, False, False, False]
    track_limits_steps = 0
    current_sector = 0

    if not ctx.reader_offline and ctx.shmm_data is not None:
        data = ctx.shmm_data
        _scor_idx, _tele_idx, player_scor, player_tele = ctx.sync.sync_player_data(data)

        scoring_info = data.scoring.scoringInfo
        if scoring_info.mLapDist > 10.0:
            ctx.track.track_length = scoring_info.mLapDist

        max_laps = scoring_info.mMaxLaps
        if max_laps > 0:
            session_laps_left = max(0.0, float(max_laps - player.current_lap))

        game_phase = int(scoring_info.mGamePhase)
        sector_flags = [int(scoring_info.mSectorFlag[i]) for i in range(3)]
        safety_car_active = game_phase == 6
        full_course_yellow_active = game_phase == 6
        session_stopped = game_phase == 7
        session_over = game_phase == 8
        has_sector_yellow = any(scoring_info.mSectorFlag[i] != 0 for i in range(3))
        local_yellow_active = has_sector_yellow
        yellow_flag_active = game_phase == 6 or local_yellow_active

        from shared_telemetry.lmu_fields import parse_yellow_flag_state

        rainfall = safe_float(scoring_info.mRaining)
        yellow_flag_state = parse_yellow_flag_state(scoring_info.mYellowFlagState)

        if player_scor is not None:
            num_penalties = max(0, int(player_scor.mNumPenalties))
            if int(player_scor.mIndividualPhase) == 10 or bool(player_scor.mUnderYellow):
                local_yellow_active = True
                yellow_flag_active = True
            blue_flag_active = int(player_scor.mFlag) == 6
            ori_fwd_x = safe_float(player_scor.mOri[2].x)
            ori_fwd_z = safe_float(player_scor.mOri[2].z)
            path_lateral = safe_float(player_scor.mPathLateral)
            current_sector = int(player_scor.mSector)

        if player_tele is not None:
            fuel_in_tank = safe_float(player_tele.mFuel)
            fuel_capacity = safe_float(player_tele.mFuelCapacity)
            is_invalid_lap = bool(player_tele.mLapInvalidated)
            from shared_telemetry.lmu_pit_limiter import pit_limiter_engaged

            pit_limiter_active = pit_limiter_engaged(player_tele)
            vel_x = safe_float(player_tele.mLocalVel.x)
            vel_y = safe_float(player_tele.mLocalVel.y)
            vel_z = safe_float(player_tele.mLocalVel.z)
            speed = math.sqrt(vel_x ** 2 + vel_y ** 2 + vel_z ** 2)

            boost_state = int(player_tele.mElectricBoostMotorState)
            if boost_state == 2:
                motor_state = 2
            elif boost_state == 3:
                motor_state = 3
            else:
                motor_state = 1

            battery_charge = safe_float(player_tele.mStateOfCharge)
            time_gap_car_ahead = safe_float(player_tele.mTimeGapCarAhead)
            time_gap_car_behind = safe_float(player_tele.mTimeGapCarBehind)
            time_gap_place_ahead = safe_float(player_tele.mTimeGapPlaceAhead)
            time_gap_place_behind = safe_float(player_tele.mTimeGapPlaceBehind)
            local_accel_x = safe_float(player_tele.mLocalAccel.x)
            local_accel_y = safe_float(player_tele.mLocalAccel.y)
            local_accel_z = safe_float(player_tele.mLocalAccel.z)
            track_limits_steps = int(player_tele.mTrackLimitsSteps)
            for i in range(4):
                tyre_flat[i] = bool(player_tele.mWheels[i].mFlat)
            damage_fields = damage_fields_from_player_telemetry(player_tele)
    else:
        vel_x = vel_y = vel_z = 0.0
        if session.time_remaining > 0:
            session_laps_left = -1.0

        current_lap = player.current_lap
        if frame_state.last_lap == 0:
            frame_state.simulated_fuel = 100.0
            frame_state.last_lap = current_lap
        elif current_lap > frame_state.last_lap:
            laps_diff = current_lap - frame_state.last_lap
            frame_state.simulated_fuel = max(0.0, frame_state.simulated_fuel - (3.5 * laps_diff))
            frame_state.last_lap = current_lap

        fuel_in_tank = frame_state.simulated_fuel
        fuel_capacity = 100.0
        is_invalid_lap = False
        pit_limiter_active = False
        speed = 50.0
        motor_state = 1
        battery_charge = 85.0

    current_lap = player.current_lap
    if frame_state.last_lap == 0 or current_lap > frame_state.last_lap:
        frame_state.lap_fuel_start = fuel_in_tank
        frame_state.lap_battery_drain = 0.0
        frame_state.lap_battery_regen = 0.0
        frame_state.last_lap = current_lap

    fuel_used_lap_raw = max(0.0, frame_state.lap_fuel_start - fuel_in_tank)
    charge_diff = battery_charge - frame_state.prev_battery_charge
    if charge_diff < 0:
        frame_state.lap_battery_drain += abs(charge_diff)
    elif charge_diff > 0:
        frame_state.lap_battery_regen += charge_diff
    frame_state.prev_battery_charge = battery_charge

    wear_fl_raw = race_state.tyres.wear[0]
    wear_fr_raw = race_state.tyres.wear[1]
    wear_rl_raw = race_state.tyres.wear[2]
    wear_rr_raw = race_state.tyres.wear[3]

    if ctx.reader_offline:
        tyre_wear_fl = (1.0 - wear_fl_raw) * 100.0
        tyre_wear_fr = (1.0 - wear_fr_raw) * 100.0
        tyre_wear_rl = (1.0 - wear_rl_raw) * 100.0
        tyre_wear_rr = (1.0 - wear_rr_raw) * 100.0
    else:
        tyre_wear_fl = wear_fl_raw * 100.0
        tyre_wear_fr = wear_fr_raw * 100.0
        tyre_wear_rl = wear_rl_raw * 100.0
        tyre_wear_rr = wear_rr_raw * 100.0

    tyre_temp_fl = race_state.tyres.carcass_temperatures[0]
    tyre_temp_fr = race_state.tyres.carcass_temperatures[1]
    tyre_temp_rl = race_state.tyres.carcass_temperatures[2]
    tyre_temp_rr = race_state.tyres.carcass_temperatures[3]

    brake_wear_fl, brake_wear_fr, brake_wear_rl, brake_wear_rr = _brake_wear_from_cache(
        ctx.cached_brake_wear
    )

    competitors_list: list[CompetitorTelemetry] = []
    if not ctx.reader_offline and ctx.shmm_data is not None:
        data = ctx.shmm_data
        scoring_info = data.scoring.scoringInfo
        veh_total = min(int(scoring_info.mNumVehicles), len(data.scoring.vehScoringInfo))

        for idx in range(veh_total):
            veh_info = data.scoring.vehScoringInfo[idx]
            if veh_info.mID > 0 and not veh_info.mIsPlayer:
                opp_tele_idx = ctx.sync._tele_indexes.get(veh_info.mID, -1)
                opp_speed = math.sqrt(
                    safe_float(veh_info.mLocalVel.x) ** 2
                    + safe_float(veh_info.mLocalVel.y) ** 2
                    + safe_float(veh_info.mLocalVel.z) ** 2
                )
                if opp_tele_idx != -1 and opp_tele_idx < len(data.telemetry.telemInfo):
                    opp_tele = data.telemetry.telemInfo[opp_tele_idx]
                    opp_speed = max(
                        opp_speed,
                        math.sqrt(
                            safe_float(opp_tele.mLocalVel.x) ** 2
                            + safe_float(opp_tele.mLocalVel.y) ** 2
                            + safe_float(opp_tele.mLocalVel.z) ** 2
                        ),
                    )

                fuel_fraction = veh_info.mFuelFraction / 255.0
                pit_requested = veh_info.mPitState == 1
                opp_lap = int(veh_info.mTotalLaps + 1)
                if opp_tele_idx != -1 and opp_tele_idx < len(data.telemetry.telemInfo):
                    opp_lap = int(data.telemetry.telemInfo[opp_tele_idx].mLapNumber)

                competitors_list.append(
                    CompetitorTelemetry(
                        driver_index=int(veh_info.mID),
                        driver_name=safe_str(veh_info.mDriverName),
                        driver_class=safe_str(veh_info.mVehicleClass),
                        standing_position=int(veh_info.mPlace),
                        class_position=int(veh_info.mPlace),
                        lap_number=opp_lap,
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
                        path_lateral=safe_float(veh_info.mPathLateral),
                    )
                )
    else:
        for opp_id, opp_data in race_state.opponents.items():
            competitors_list.append(
                CompetitorTelemetry(
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
            )

    return TelemetryFrame(
        session_type=session_type_str,
        session_type_int=session_type_int,
        session_time_left=session.time_remaining,
        session_laps_left=session_laps_left,
        lap_number=player.current_lap,
        lap_distance=player.lap_distance,
        track_length_m=ctx.track.track_length,
        path_lateral=path_lateral,
        lap_time_best=player.best_laptime,
        lap_time_previous=player.last_laptime,
        is_invalid_lap=is_invalid_lap,
        in_garage=bool(player.in_pits and race_state.inputs.throttle < 0.01),
        in_pits=player.in_pits,
        pit_limiter_active=pit_limiter_active,
        yellow_flag_active=yellow_flag_active,
        local_yellow_active=local_yellow_active,
        safety_car_active=safety_car_active,
        full_course_yellow_active=full_course_yellow_active,
        blue_flag_active=blue_flag_active,
        session_stopped=session_stopped,
        session_over=session_over,
        driver_name=driver_name,
        num_penalties=num_penalties,
        game_phase=game_phase,
        sector_flags=sector_flags,
        fuel_in_tank=fuel_in_tank,
        fuel_capacity=fuel_capacity,
        fuel_used_lap_raw=fuel_used_lap_raw,
        battery_charge=battery_charge,
        battery_drain=frame_state.lap_battery_drain,
        battery_regen=frame_state.lap_battery_regen,
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
        ori_fwd_x=ori_fwd_x,
        ori_fwd_z=ori_fwd_z,
        player_class=player.class_name,
        vehicle_name=player.vehicle_name,
        standing_position=int(player.place),
        time_gap_car_ahead=time_gap_car_ahead,
        time_gap_car_behind=time_gap_car_behind,
        time_gap_place_ahead=time_gap_place_ahead,
        time_gap_place_behind=time_gap_place_behind,
        competitors=competitors_list,
        damage_aero=float(damage_fields["damage_aero"]),
        suspension_damage=float(damage_fields["suspension_damage"]),
        dent_severity_avg=float(damage_fields["dent_severity_avg"]),
        dent_severity_max=int(damage_fields["dent_severity_max"]),
        detached=bool(damage_fields["detached"]),
        last_impact_et=float(damage_fields["last_impact_et"]),
        last_impact_magnitude=float(damage_fields["last_impact_magnitude"]),
        raining_intensity=rainfall,
        yellow_flag_state=yellow_flag_state,
        local_accel_x=local_accel_x,
        local_accel_y=local_accel_y,
        local_accel_z=local_accel_z,
        tyre_flat_fl=tyre_flat[0],
        tyre_flat_fr=tyre_flat[1],
        tyre_flat_rl=tyre_flat[2],
        tyre_flat_rr=tyre_flat[3],
        track_limits_steps=track_limits_steps,
        current_sector=current_sector,
    )
