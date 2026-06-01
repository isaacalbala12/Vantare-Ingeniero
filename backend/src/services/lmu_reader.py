import math
import logging
from typing import Optional, Dict, Any

from shared_telemetry.pyLMUSharedMemory.lmu_mmap import MMapControl
from shared_telemetry.pyLMUSharedMemory.lmu_data import (
    LMUObjectOut,
    LMUConstants,
)

logger = logging.getLogger("vantare.lmu_reader")


def decode_name(byte_arr) -> str:
    """Decode ctypes char array to string. Handles leading null byte and null terminators."""
    if byte_arr is None:
        return ""
    if not isinstance(byte_arr, (bytes, bytearray)):
        try:
            byte_arr = bytes(byte_arr)
        except Exception:
            return ""
    if len(byte_arr) == 0:
        return ""
    if byte_arr[0] == 0 and len(byte_arr) > 1:
        byte_arr = byte_arr[1:]
    null_pos = byte_arr.find(b"\x00")
    if null_pos >= 0:
        byte_arr = byte_arr[:null_pos]
    if len(byte_arr) == 0:
        return ""
    try:
        return byte_arr.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        try:
            return byte_arr.decode("latin-1").strip()
        except Exception:
            return byte_arr.decode("utf-8", errors="replace").strip()


def calculate_rotation(orientation: dict) -> Dict[str, float]:
    """Extract yaw/pitch/roll from 3x3 orientation matrix. NaN/Inf → 0,0,0."""
    rx = orientation["row_x"]
    ry = orientation["row_y"]
    rz = orientation["row_z"]
    yaw = math.atan2(rz["x"], rz["z"])
    pitch = math.atan2(-ry["z"], math.sqrt(rx["z"] ** 2 + rz["z"] ** 2))
    roll = math.atan2(ry["x"], math.sqrt(rx["x"] ** 2 + rz["x"] ** 2))
    if math.isnan(yaw) or math.isinf(yaw):
        yaw, pitch, roll = 0.0, 0.0, 0.0
    return {"yaw": yaw, "pitch": pitch, "roll": roll}


def orientation_to_dict(orient) -> Dict:
    """Convert ctypes LMUVect3*3 array to dict format.

    Handles both struct-style (row_x/y/z) and array-style (orient[0],[1],[2]).
    """
    if hasattr(orient, "row_x"):
        return {
            "row_x": {"x": orient.row_x.x, "y": orient.row_x.y, "z": orient.row_x.z},
            "row_y": {"x": orient.row_y.x, "y": orient.row_y.y, "z": orient.row_y.z},
            "row_z": {"x": orient.row_z.x, "y": orient.row_z.y, "z": orient.row_z.z},
        }
    if hasattr(orient, "__getitem__") and len(orient) >= 3:
        return {
            "row_x": {"x": orient[0].x, "y": orient[0].y, "z": orient[0].z},
            "row_y": {"x": orient[1].x, "y": orient[1].y, "z": orient[1].z},
            "row_z": {"x": orient[2].x, "y": orient[2].y, "z": orient[2].z},
        }
    raise ValueError(f"Unknown orientation format: {type(orient)}")


class LMUReader:
    """Lee shared memory de LMU usando MMapControl.

    Los structs ctypes tienen nombres específicos:
    - data.scoring.scoringInfo (NO mScoringInfo)
    - data.scoring.vehScoringInfo (NO mVehicles)
    - data.telemetry.playerVehicleIdx (NO data.player_index)
    - Player telemetry: data.telemetry.telemInfo[playerIdx]
    """

    def __init__(self):
        self._shmm = None
        self._is_initialized = False

    def _create_mmap(self):
        """Crear MMapControl con el nombre correcto y struct LMUObjectOut."""
        mmap = MMapControl(LMUConstants.LMU_SHARED_MEMORY_FILE, LMUObjectOut)
        mmap.create(access_mode=0)  # Copy mode (thread-safe)
        return mmap

    def get_flat_dict(self) -> Dict[str, Any]:
        """Lee shared memory y devuelve dict plano.

        CRITICAL: Los nombres de campo deben coincidir con los structs en lmu_data.py.
        """
        if not self._is_initialized:
            try:
                self._shmm = self._create_mmap()
                self._is_initialized = True
            except Exception as e:
                logger.error(f"Failed to init LMU shared memory: {e}")
                return {"session_running_time": 0.0}

        if self._shmm is None or self._shmm.data is None:
            return {"session_running_time": 0.0}

        # Copiar buffer (thread-safe)
        self._shmm.update()

        d: Dict[str, Any] = {}
        try:
            data = self._shmm.data
            player_idx = int(data.telemetry.playerVehicleIdx)

            # ---- Session info (scoringInfo) ----
            si = data.scoring.scoringInfo
            d["session_type"] = int(si.mSession)
            d["session_phase"] = int(si.mGamePhase)
            d["session_running_time"] = float(si.mCurrentET)
            d["session_time_remaining"] = float(si.mEndET) - float(si.mCurrentET)
            d["track_length"] = float(si.mLapDist)

            # ---- Player scoring (vehScoringInfo[playerIdx]) ----
            pv = data.scoring.vehScoringInfo[player_idx]
            d["place"] = int(pv.mPlace)
            d["lap_number"] = int(pv.mTotalLaps)
            d["lap_distance"] = float(pv.mLapDist)
            # LMU sector: 0=sector3, 1=sector1, 2=sector2
            raw_sector = int(pv.mSector)
            d["sector_number"] = raw_sector if raw_sector != 0 else 3
            d["in_pits"] = bool(pv.mInPits)
            d["driver_name"] = decode_name(pv.mDriverName)

            # Orientation matrix (mOri as LMUVect3*3)
            try:
                orient = orientation_to_dict(pv.mOri)
                rot = calculate_rotation(orient)
                d["rotation_yaw"] = rot["yaw"]
                d["rotation_pitch"] = rot["pitch"]
                d["rotation_roll"] = rot["roll"]
            except (ValueError, AttributeError, TypeError):
                d["rotation_yaw"] = 0.0
                d["rotation_pitch"] = 0.0
                d["rotation_roll"] = 0.0

            # Fuel fraction (0-255 → percentage)
            fuel_frac = int(pv.mFuelFraction)
            if fuel_frac > 0:
                d["fuel_fraction"] = fuel_frac / 255.0 * 100.0

            # DRS state
            d["drs_active"] = bool(getattr(pv, "mDRSState", False))

            # ---- Player telemetry (telemInfo[playerIdx]) ----
            pt = data.telemetry.telemInfo[player_idx]

            # Speed: LMU no tiene campo mSpeed, usar mLocalVel.x (forward velocity m/s)
            d["speed_ms"] = abs(float(pt.mLocalVel.x))
            d["world_x"] = float(pt.mPos.x)
            d["world_y"] = float(pt.mPos.y)
            d["world_z"] = float(pt.mPos.z)
            d["engine_rpm"] = float(pt.mEngineRPM)
            d["gear"] = int(pt.mGear)
            d["water_temp"] = float(pt.mEngineWaterTemp)
            d["oil_temp"] = float(pt.mEngineOilTemp)
            d["fuel_left"] = float(pt.mFuel)
            d["fuel_capacity"] = float(getattr(pt, "mFuelCapacity", 0))
            d["virtual_energy"] = float(getattr(pt, "mVirtualEnergy", 0))
            d["state_of_charge"] = float(getattr(pt, "mStateOfCharge", 0))
            d["battery_charge_fraction"] = float(getattr(pt, "mBatteryChargeFraction", 0))

            # Acceleration (crash detection)
            if hasattr(pt, "mLocalAccel"):
                d["accel_long"] = float(pt.mLocalAccel.x)
                d["accel_lat"] = float(pt.mLocalAccel.y)
                d["accel_vert"] = float(pt.mLocalAccel.z)

            # Wheels
            # mTemperature es c_double*3 (left/center/right Kelvin). Tomamos center y convertimos a Celsius.
            _kelvin_to_c = lambda k: k - 273.15 if k > 100 else k
            d["tyre_temp_fl"] = _kelvin_to_c(float(pt.mWheels[0].mTemperature[1]))
            d["tyre_temp_fr"] = _kelvin_to_c(float(pt.mWheels[1].mTemperature[1]))
            d["tyre_temp_rl"] = _kelvin_to_c(float(pt.mWheels[2].mTemperature[1]))
            d["tyre_temp_rr"] = _kelvin_to_c(float(pt.mWheels[3].mTemperature[1]))
            d["tyre_wear_fl"] = float(pt.mWheels[0].mWear)
            d["tyre_wear_fr"] = float(pt.mWheels[1].mWear)
            d["tyre_wear_rl"] = float(pt.mWheels[2].mWear)
            d["tyre_wear_rr"] = float(pt.mWheels[3].mWear)
            d["brake_temp_fl"] = float(pt.mWheels[0].mBrakeTemp)
            d["brake_temp_fr"] = float(pt.mWheels[1].mBrakeTemp)
            d["brake_temp_rl"] = float(pt.mWheels[2].mBrakeTemp)
            d["brake_temp_rr"] = float(pt.mWheels[3].mBrakeTemp)
            d["tyre_pressure_fl"] = float(pt.mWheels[0].mPressure)
            d["tyre_pressure_fr"] = float(pt.mWheels[1].mPressure)
            d["tyre_pressure_rl"] = float(pt.mWheels[2].mPressure)
            d["tyre_pressure_rr"] = float(pt.mWheels[3].mPressure)

            # Tyre compound names
            d["tyre_compound_fl"] = decode_name(getattr(pt, "mFrontTireCompoundName", b""))
            d["tyre_compound_rl"] = decode_name(getattr(pt, "mRearTireCompoundName", b""))

            # ---- Oponents (vehScoringInfo) ----
            rivals = []
            num_veh = int(si.mNumVehicles)
            for i in range(min(num_veh, LMUConstants.MAX_MAPPED_VEHICLES)):
                if i == player_idx:
                    continue
                veh = data.scoring.vehScoringInfo[i]
                name = decode_name(veh.mDriverName)
                if name.lower() == "transparent trainer":
                    continue

                # Gap: use time behind leader as approximation
                gap = float(veh.mTimeBehindLeader)

                rivals.append({
                    "driver_raw_name": name,
                    "car_number": str(int(getattr(veh, "mID", -1))),
                    "place": int(veh.mPlace),
                    "class_place": int(veh.mPlace),  # No class_place in struct
                    "speed": 0.0,
                    "distance_round_track": float(getattr(veh, "mLapDist", 0)),
                    "laps_completed": int(veh.mTotalLaps),
                    "last_lap_time": float(getattr(veh, "mLastLapTime", 0)),
                    "best_lap_time": float(getattr(veh, "mBestLapTime", 0)),
                    "current_sector": int(veh.mSector) if int(veh.mSector) != 0 else 3,
                    "in_pits": bool(veh.mInPits),
                    "vehicle_class": decode_name(veh.mVehicleClass),
                    "tyre_compound": "Unknown_Race",
                    "gap_to_player": gap,
                    "is_active": True,
                    "world_x": 0.0,
                    "world_z": 0.0,
                })

            # Fill speeds/positions from telemetry array
            for i, rival in enumerate(rivals):
                if i < LMUConstants.MAX_MAPPED_VEHICLES:
                    try:
                        ot = data.telemetry.telemInfo[i]
                        rival["speed"] = abs(float(ot.mLocalVel.x))
                        rival["world_x"] = float(ot.mPos.x)
                        rival["world_z"] = float(ot.mPos.z)
                        rival["tyre_compound"] = decode_name(
                            getattr(ot, "mFrontTireCompoundName", b"")
                        )
                    except Exception:
                        pass

            d["rivals"] = rivals
            d["num_rivals"] = len(rivals)

        except Exception as e:
            logger.error(f"Error reading LMU shared memory: {e}", exc_info=True)
            return {"session_running_time": 0.0}

        return d

    def reinitialize(self) -> bool:
        import subprocess
        try:
            r = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq LMU.exe"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "LMU.exe" not in r.stdout:
                logger.info("LMU no está corriendo")
                return False
        except Exception:
            pass
        self._shmm = self._create_mmap()
        self._is_initialized = True
        logger.info("Shared memory reinitialized")
        return True
