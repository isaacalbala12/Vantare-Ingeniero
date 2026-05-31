"""
Telemetry reader interface for Le Mans Ultimate.

Handles reading shared memory in a separate thread, parsing it into Pydantic models,
providing synchronization of scoring and telemetry arrays, and supporting an
offline simulated/mock mode with manual state injection.
"""

import threading
import time
from math import isfinite
from typing import Any

from .pyLMUSharedMemory.lmu_data import LMUObjectOut, LMUConstants
from .pyLMUSharedMemory.lmu_mmap import MMapControl

from .models import (
    RaceState,
    SessionData,
    VehicleData,
    TyreData,
    BrakeData,
    EngineData,
    DriverInputs,
)
from .sync import TelemetrySync


# Helper Functions
def infnan_to_zero(value: Any) -> float:
    """Convert infinite or NaN values to 0.0 for safety."""
    if isinstance(value, (int, float)) and isfinite(value):
        return float(value)
    return 0.0


def bytes_to_str(bytestring: bytes | Any, char_encoding: str = "utf-8") -> str:
    """Safely convert ctypes byte arrays/strings to Python strings."""
    if isinstance(bytestring, bytes):
        return bytestring.decode(encoding=char_encoding, errors="replace").rstrip("\0 ").rstrip()
    return ""


class TelemetryReader:
    """Thread-safe telemetry reader for LMU shared memory."""

    def __init__(self, offline: bool = False, poll_rate: float = 0.05) -> None:
        """Initialize the telemetry reader.

        Args:
            offline: If True, do not try to open LMU shared memory; run in simulated mode.
            poll_rate: Polling frequency in seconds (default 0.05s / 50ms).
        """
        self.offline = offline
        self.poll_rate = poll_rate

        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._sync = TelemetrySync()

        # Holds current RaceState
        self._state = None
        # Holds manually injected state in offline mode
        self._injected_state = None

        if not self.offline:
            # Initialize LMU shared memory map control using copy mode (access_mode=0)
            self.shmm = MMapControl(LMUConstants.LMU_SHARED_MEMORY_FILE, LMUObjectOut)
        else:
            self.shmm = None

        # Pre-populate default state
        self._state = self._get_default_state()

    def start(self) -> None:
        """Start the background polling thread."""
        with self._lock:
            if self._running:
                return
            self._running = True

        if not self.offline:
            # Create the shared memory mapping (mode 0 is buffer copy)
            self.shmm.create(access_mode=0)

        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background polling thread and clean up resources."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

        if not self.offline and self.shmm is not None:
            self.shmm.close()

    def get_state(self) -> RaceState:
        """Get the current thread-safe RaceState.

        Returns:
            The parsed or simulated RaceState.
        """
        with self._lock:
            return self._state

    def inject_state(self, state: RaceState) -> None:
        """Inject a manual RaceState (available in offline mode).

        Args:
            state: The RaceState to inject.
        """
        with self._lock:
            self._injected_state = state
            self._state = state

    def _read_loop(self) -> None:
        """Background thread worker loop."""
        start_time = time.monotonic()

        while True:
            # Thread-safe check for running state
            with self._lock:
                if not self._running:
                    break

            try:
                if self.offline:
                    with self._lock:
                        injected = self._injected_state

                    if injected is not None:
                        # Keep the injected state but update timestamp
                        updated_state = injected.model_copy(
                            update={"timestamp": time.monotonic()}
                        )
                        with self._lock:
                            self._state = updated_state
                    else:
                        # Simulated generation
                        elapsed = time.monotonic() - start_time
                        simulated = self._generate_mock_state(elapsed)
                        with self._lock:
                            self._state = simulated
                else:
                    # Poll shared memory update
                    self.shmm.update()
                    parsed = self._parse_shared_memory()
                    if parsed is not None:
                        with self._lock:
                            self._state = parsed

            except Exception as e:
                # Catch-all to prevent thread dying silently
                import traceback
                traceback.print_exc()

            time.sleep(self.poll_rate)

    def _get_default_state(self) -> RaceState:
        """Construct a zeroed default RaceState."""
        return RaceState(
            session=SessionData(
                session_type=0,
                time_remaining=0.0,
                track_temp=0.0,
                ambient_temp=0.0,
                wetness_average=0.0,
                raininess=0.0,
                track_name="",
            ),
            player=VehicleData(
                slot_id=-1,
                driver_name="Offline Player",
                vehicle_name="Prototype Hybrid",
                class_name="LMH",
                place=1,
                in_pits=False,
                lap_distance=0.0,
                track_progress=0.0,
                current_lap=1,
                last_laptime=0.0,
                best_laptime=0.0,
                position_xyz=(0.0, 0.0, 0.0),
            ),
            tyres=TyreData(
                compound_name=["Medium", "Medium", "Medium", "Medium"],
                wear=[0.0, 0.0, 0.0, 0.0],
                pressures=[0.0, 0.0, 0.0, 0.0],
                temperatures_ico=[(0.0, 0.0, 0.0)] * 4,
                carcass_temperatures=[0.0, 0.0, 0.0, 0.0],
            ),
            brakes=BrakeData(
                temperatures=[0.0, 0.0, 0.0, 0.0],
                wear_thickness=[0.0, 0.0, 0.0, 0.0],
                bias_front=0.0,
            ),
            engine=EngineData(
                gear=0,
                rpm=0.0,
                max_rpm=0.0,
                water_temp=0.0,
                oil_temp=0.0,
                lift_and_coast_progress=0.0,
            ),
            inputs=DriverInputs(
                throttle=0.0,
                brake=0.0,
                clutch=0.0,
                steering=0.0,
            ),
            opponents={},
            timestamp=time.monotonic(),
        )

    def _generate_mock_state(self, elapsed: float) -> RaceState:
        """Generate evolving simulated mock telemetry data."""
        import math

        # Cycles and patterns for mock values
        cycle = (elapsed % 15.0) / 15.0  # 15 second throttle cycle
        speed = 80.0 + 190.0 * cycle     # km/h
        rpm = 3000.0 + 5200.0 * (cycle if cycle < 0.9 else (1.0 - cycle) / 0.1)
        gear = int(2 + (speed / 50.0))

        # Circle-like motion coordinate generation
        angle = (elapsed % 90.0) / 90.0 * 2.0 * math.pi
        pos_x = 450.0 * math.cos(angle)
        pos_z = 450.0 * math.sin(angle)
        pos_y = 15.0 + 1.5 * math.sin(elapsed)

        # Tire wear decreasing
        wear_fl = max(0.0, 1.0 - elapsed * 0.00005)
        wear_fr = max(0.0, 1.0 - elapsed * 0.00005)
        wear_rl = max(0.0, 1.0 - elapsed * 0.00008)
        wear_rr = max(0.0, 1.0 - elapsed * 0.00008)

        session = SessionData(
            session_type=4,  # Race
            time_remaining=max(0.0, 7200.0 - elapsed),
            track_temp=31.2 + 0.3 * math.sin(elapsed / 120.0),
            ambient_temp=22.5,
            wetness_average=0.0,
            raininess=0.0,
            track_name="Spa-Francorchamps",
        )

        player = VehicleData(
            slot_id=0,
            driver_name="Isaac",
            vehicle_name="Vantare Ingeniero Hypercar",
            class_name="LMH",
            place=2,
            in_pits=False,
            lap_distance=float((speed / 3.6) * elapsed % 7004.0),
            track_progress=float(((speed / 3.6) * elapsed % 7004.0) / 7004.0),
            current_lap=int(1 + ((speed / 3.6) * elapsed // 7004.0)),
            last_laptime=142.15,
            best_laptime=141.88,
            position_xyz=(pos_x, pos_y, pos_z),
        )

        tyres = TyreData(
            compound_name=["Soft", "Soft", "Soft", "Soft"],
            wear=[wear_fl, wear_fr, wear_rl, wear_rr],
            pressures=[205.2, 206.1, 198.8, 199.5],
            temperatures_ico=[
                (78.5, 79.4, 77.2),
                (79.0, 80.2, 78.1),
                (84.1, 85.3, 83.0),
                (84.6, 85.9, 83.5),
            ],
            carcass_temperatures=[75.2, 76.1, 80.4, 81.0],
        )

        brakes = BrakeData(
            temperatures=[310.5, 312.4, 260.1, 262.3],
            wear_thickness=[0.027, 0.027, 0.025, 0.025],
            bias_front=0.55,
        )

        engine = EngineData(
            gear=gear,
            rpm=rpm,
            max_rpm=8800.0,
            water_temp=85.4,
            oil_temp=92.1,
            lift_and_coast_progress=0.0,
        )

        inputs = DriverInputs(
            throttle=float(max(0.0, min(1.0, 0.9 * cycle + 0.1 * math.sin(elapsed)))),
            brake=float(
                max(0.0, min(1.0, 0.8 * (1.0 - cycle) if cycle > 0.85 else 0.0))
            ),
            clutch=0.0,
            steering=float(0.08 * math.sin(elapsed / 3.0)),
        )

        # Generate a simulated opponent in 1st place
        opp_progress = float(((speed / 3.6) * (elapsed + 3.0) % 7004.0) / 7004.0)
        opponent = VehicleData(
            slot_id=1,
            driver_name="Rival AI",
            vehicle_name="Challenger Prototype",
            class_name="LMH",
            place=1,
            in_pits=False,
            lap_distance=float((speed / 3.6) * (elapsed + 3.0) % 7004.0),
            track_progress=opp_progress,
            current_lap=int(1 + ((speed / 3.6) * (elapsed + 3.0) // 7004.0)),
            last_laptime=141.92,
            best_laptime=141.52,
            position_xyz=(pos_x + 15.0, pos_y, pos_z + 15.0),
        )

        return RaceState(
            session=session,
            player=player,
            tyres=tyres,
            brakes=brakes,
            engine=engine,
            inputs=inputs,
            opponents={1: opponent},
            timestamp=time.monotonic(),
        )

    def _parse_shared_memory(self) -> RaceState | None:
        """Parse raw ctypes structures from LMU shared memory into Pydantic models."""
        data = self.shmm.data
        if not data:
            return None

        # 1. Parse SessionData
        scoring_info = data.scoring.scoringInfo
        session = SessionData(
            session_type=scoring_info.mSession,
            time_remaining=infnan_to_zero(scoring_info.mSessionTimeRemaining),
            track_temp=infnan_to_zero(scoring_info.mTrackTemp),
            ambient_temp=infnan_to_zero(scoring_info.mAmbientTemp),
            wetness_average=infnan_to_zero(scoring_info.mAvgPathWetness),
            raininess=infnan_to_zero(scoring_info.mRaining),
            track_name=bytes_to_str(scoring_info.mTrackName),
        )

        # 2. Synchronize player indices and retrieve data references
        scor_idx, tele_idx, player_scor, player_tele = self._sync.sync_player_data(
            data
        )

        # If player scoring is not found yet (e.g. during session loading / waiting room)
        if player_scor is None:
            return RaceState(
                session=session,
                player=VehicleData(
                    slot_id=-1,
                    driver_name="Unknown Player",
                    vehicle_name="Unknown Vehicle",
                    class_name="Unknown",
                    place=0,
                    in_pits=False,
                    lap_distance=0.0,
                    track_progress=0.0,
                    current_lap=0,
                    last_laptime=0.0,
                    best_laptime=0.0,
                    position_xyz=(0.0, 0.0, 0.0),
                ),
                tyres=TyreData(
                    compound_name=["", "", "", ""],
                    wear=[0.0, 0.0, 0.0, 0.0],
                    pressures=[0.0, 0.0, 0.0, 0.0],
                    temperatures_ico=[(0.0, 0.0, 0.0)] * 4,
                    carcass_temperatures=[0.0, 0.0, 0.0, 0.0],
                ),
                brakes=BrakeData(
                    temperatures=[0.0, 0.0, 0.0, 0.0],
                    wear_thickness=[0.0, 0.0, 0.0, 0.0],
                    bias_front=0.0,
                ),
                engine=EngineData(
                    gear=0,
                    rpm=0.0,
                    max_rpm=0.0,
                    water_temp=0.0,
                    oil_temp=0.0,
                    lift_and_coast_progress=0.0,
                ),
                inputs=DriverInputs(
                    throttle=0.0,
                    brake=0.0,
                    clutch=0.0,
                    steering=0.0,
                ),
                opponents={},
                timestamp=time.monotonic(),
            )

        # 3. Process Player VehicleData
        track_len = infnan_to_zero(scoring_info.mLapDist)
        track_progress = 0.0
        if track_len > 0.0:
            track_progress = infnan_to_zero(player_scor.mLapDist / track_len)
            track_progress = max(0.0, min(1.0, track_progress))

        current_lap = int(player_scor.mTotalLaps + 1)
        if player_tele is not None:
            current_lap = int(player_tele.mLapNumber)

        player = VehicleData(
            slot_id=player_scor.mID,
            driver_name=bytes_to_str(player_scor.mDriverName),
            vehicle_name=bytes_to_str(player_scor.mVehicleName),
            class_name=bytes_to_str(player_scor.mVehicleClass),
            place=int(player_scor.mPlace),
            in_pits=bool(player_scor.mInPits),
            lap_distance=infnan_to_zero(player_scor.mLapDist),
            track_progress=track_progress,
            current_lap=current_lap,
            last_laptime=infnan_to_zero(player_scor.mLastLapTime),
            best_laptime=infnan_to_zero(player_scor.mBestLapTime),
            position_xyz=(
                infnan_to_zero(player_scor.mPos.x),
                infnan_to_zero(player_scor.mPos.y),
                infnan_to_zero(player_scor.mPos.z),
            ),
        )

        # 4. Process Tyres, Brakes, Engine, Inputs (telemetry-based)
        if player_tele is not None:
            # Tire Compound names mapping
            t_front = bytes_to_str(player_tele.mFrontTireCompoundName)
            t_rear = bytes_to_str(player_tele.mRearTireCompoundName)
            compound_names = [t_front, t_front, t_rear, t_rear]

            wear = []
            pressures = []
            temperatures_ico = []
            carcass_temps = []
            brake_temps = []

            for i in range(4):
                w = player_tele.mWheels[i]
                wear.append(infnan_to_zero(w.mWear))
                pressures.append(infnan_to_zero(w.mPressure))
                # Kelvin to Celsius conversion
                temperatures_ico.append(
                    (
                        infnan_to_zero(w.mTemperature[0]) - 273.15,
                        infnan_to_zero(w.mTemperature[1]) - 273.15,
                        infnan_to_zero(w.mTemperature[2]) - 273.15,
                    )
                )
                carcass_temps.append(
                    infnan_to_zero(w.mTireCarcassTemperature) - 273.15
                )
                # Brake temperature is also in Kelvin in telemetry output
                brake_temps.append(infnan_to_zero(w.mBrakeTemp) - 273.15)

            tyres = TyreData(
                compound_name=compound_names,
                wear=wear,
                pressures=pressures,
                temperatures_ico=temperatures_ico,
                carcass_temperatures=carcass_temps,
            )

            brakes = BrakeData(
                temperatures=brake_temps,
                wear_thickness=[0.0, 0.0, 0.0, 0.0],
                bias_front=1.0 - infnan_to_zero(player_tele.mRearBrakeBias),
            )

            engine = EngineData(
                gear=int(player_tele.mGear),
                rpm=infnan_to_zero(player_tele.mEngineRPM),
                max_rpm=infnan_to_zero(player_tele.mEngineMaxRPM),
                water_temp=infnan_to_zero(player_tele.mEngineWaterTemp),
                oil_temp=infnan_to_zero(player_tele.mEngineOilTemp),
                lift_and_coast_progress=float(player_tele.mLiftAndCoastProgress),
            )

            inputs = DriverInputs(
                throttle=infnan_to_zero(player_tele.mFilteredThrottle),
                brake=infnan_to_zero(player_tele.mFilteredBrake),
                clutch=infnan_to_zero(player_tele.mFilteredClutch),
                steering=infnan_to_zero(player_tele.mFilteredSteering),
            )
        else:
            # Fallback zeroed states if player telemetry isn't available
            tyres = TyreData(
                compound_name=["", "", "", ""],
                wear=[0.0, 0.0, 0.0, 0.0],
                pressures=[0.0, 0.0, 0.0, 0.0],
                temperatures_ico=[(0.0, 0.0, 0.0)] * 4,
                carcass_temperatures=[0.0, 0.0, 0.0, 0.0],
            )
            brakes = BrakeData(
                temperatures=[0.0, 0.0, 0.0, 0.0],
                wear_thickness=[0.0, 0.0, 0.0, 0.0],
                bias_front=0.0,
            )
            engine = EngineData(
                gear=0,
                rpm=0.0,
                max_rpm=0.0,
                water_temp=0.0,
                oil_temp=0.0,
                lift_and_coast_progress=0.0,
            )
            inputs = DriverInputs(
                throttle=0.0,
                brake=0.0,
                clutch=0.0,
                steering=0.0,
            )

        # 5. Process Opponents Data
        opponents = {}
        veh_total = min(
            int(scoring_info.mNumVehicles), len(data.scoring.vehScoringInfo)
        )
        for idx in range(veh_total):
            veh_info = data.scoring.vehScoringInfo[idx]
            # Verify it's an active opponent and not the player
            if not veh_info.mIsPlayer and veh_info.mID > 0:
                opp_progress = 0.0
                if track_len > 0.0:
                    opp_progress = infnan_to_zero(veh_info.mLapDist / track_len)
                    opp_progress = max(0.0, min(1.0, opp_progress))

                opponents[int(veh_info.mID)] = VehicleData(
                    slot_id=int(veh_info.mID),
                    driver_name=bytes_to_str(veh_info.mDriverName),
                    vehicle_name=bytes_to_str(veh_info.mVehicleName),
                    class_name=bytes_to_str(veh_info.mVehicleClass),
                    place=int(veh_info.mPlace),
                    in_pits=bool(veh_info.mInPits),
                    lap_distance=infnan_to_zero(veh_info.mLapDist),
                    track_progress=opp_progress,
                    current_lap=int(veh_info.mTotalLaps + 1),
                    last_laptime=infnan_to_zero(veh_info.mLastLapTime),
                    best_laptime=infnan_to_zero(veh_info.mBestLapTime),
                    position_xyz=(
                        infnan_to_zero(veh_info.mPos.x),
                        infnan_to_zero(veh_info.mPos.y),
                        infnan_to_zero(veh_info.mPos.z),
                    ),
                )

        return RaceState(
            session=session,
            player=player,
            tyres=tyres,
            brakes=brakes,
            engine=engine,
            inputs=inputs,
            opponents=opponents,
            timestamp=time.monotonic(),
        )
