import ctypes
import math
import logging
from typing import Optional, Dict, Any
from shared_telemetry.pyLMUSharedMemory.lmu_mmap import MMapControl

logger = logging.getLogger("vantare.lmu_reader")


def decode_name(byte_arr) -> str:
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
    def __init__(self):
        self._shmm = None
        self._is_initialized = False

    def _create_mmap(self):
        mmap = MMapControl()
        mmap.create("$LMULocal$", 0)
        return mmap

    def get_flat_dict(self) -> Dict[str, Any]:
        if not self._is_initialized:
            try:
                self._shmm = self._create_mmap()
                self._is_initialized = True
            except Exception as e:
                logger.error(f"Failed to init LMU shared memory: {e}")
                return {"session_running_time": 0.0}
        if self._shmm is None or self._shmm.data is None:
            return {"session_running_time": 0.0}
        d: Dict[str, Any] = {}
        try:
            data = self._shmm.data
            scoring = data.scoring
            d["session_type"] = int(scoring.mScoringInfo.mSession)
            d["session_phase"] = int(scoring.mScoringInfo.mGamePhase)
            d["session_running_time"] = float(scoring.mScoringInfo.mCurrentET)
            end_et = float(scoring.mScoringInfo.mEndET)
            d["session_time_remaining"] = end_et - float(scoring.mScoringInfo.mCurrentET)
            d["track_length"] = float(scoring.mScoringInfo.mLapDist)
            player_veh = scoring.mVehicles[data.player_index]
            d["place"] = int(player_veh.mPlace)
            d["lap_number"] = int(player_veh.mTotalLaps)
            d["lap_distance"] = float(player_veh.mLapDist)
            d["sector_number"] = int(player_veh.mSector) if player_veh.mSector != 0 else 3
            d["in_pits"] = bool(player_veh.mInPits)
            d["driver_name"] = decode_name(player_veh.mDriverName)
            try:
                orient = orientation_to_dict(player_veh.mOrientation)
                rot = calculate_rotation(orient)
                d["rotation_yaw"] = rot["yaw"]
                d["rotation_pitch"] = rot["pitch"]
                d["rotation_roll"] = rot["roll"]
            except (ValueError, AttributeError, TypeError):
                d["rotation_yaw"] = 0.0
                d["rotation_pitch"] = 0.0
                d["rotation_roll"] = 0.0
            d["virtual_energy"] = float(getattr(player_veh, "mVirtualEnergy", 0))
            tele = data.telemetry
            d["speed_ms"] = float(tele.mSpeed)
            d["world_x"] = float(tele.mPos.x)
            d["world_y"] = float(tele.mPos.y)
            d["world_z"] = float(tele.mPos.z)
            d["engine_rpm"] = float(tele.mEngineRPM)
            d["gear"] = int(tele.mGear)
            d["water_temp"] = float(tele.mEngineWaterTemp)
            d["oil_temp"] = float(tele.mEngineOilTemp)
            d["fuel_left"] = float(tele.mFuel)
            d["fuel_capacity"] = float(getattr(tele, "mFuelCapacity", 0))
            d["tyre_temp_fl"] = float(tele.mWheels[0].mTemperature)
            d["tyre_temp_fr"] = float(tele.mWheels[1].mTemperature)
            d["tyre_temp_rl"] = float(tele.mWheels[2].mTemperature)
            d["tyre_temp_rr"] = float(tele.mWheels[3].mTemperature)
            d["tyre_wear_fl"] = float(tele.mWheels[0].mWear)
            d["tyre_wear_fr"] = float(tele.mWheels[1].mWear)
            d["tyre_wear_rl"] = float(tele.mWheels[2].mWear)
            d["tyre_wear_rr"] = float(tele.mWheels[3].mWear)
            d["brake_temp_fl"] = float(tele.mWheels[0].mBrakeTemp)
            d["brake_temp_fr"] = float(tele.mWheels[1].mBrakeTemp)
            d["brake_temp_rl"] = float(tele.mWheels[2].mBrakeTemp)
            d["brake_temp_rr"] = float(tele.mWheels[3].mBrakeTemp)
            d["tyre_pressure_fl"] = float(tele.mWheels[0].mPressure)
            d["tyre_pressure_fr"] = float(tele.mWheels[1].mPressure)
            d["tyre_pressure_rl"] = float(tele.mWheels[2].mPressure)
            d["tyre_pressure_rr"] = float(tele.mWheels[3].mPressure)
            if hasattr(tele, "mLocalAccel"):
                d["accel_long"] = float(tele.mLocalAccel.x)
                d["accel_lat"] = float(tele.mLocalAccel.y)
                d["accel_vert"] = float(tele.mLocalAccel.z)
            d["state_of_charge"] = float(getattr(tele, "mStateOfCharge", 0))
            d["battery_charge_fraction"] = float(getattr(tele, "mBatteryChargeFraction", 0))
            rivals = []
            num_veh = int(scoring.mScoringInfo.mNumVehicles)
            for i in range(min(num_veh, 64)):
                if i == data.player_index:
                    continue
                veh = scoring.mVehicles[i]
                name = decode_name(veh.mDriverName)
                if name.lower() == "transparent trainer":
                    continue
                rivals.append({
                    "driver_raw_name": name,
                    "car_number": decode_name(getattr(veh, "mCarNumber", b"")),
                    "place": int(veh.mPlace),
                    "class_place": int(getattr(veh, "mClassPlace", 0)),
                    "speed": 0.0,
                    "distance_round_track": float(getattr(veh, "mLapDist", 0)),
                    "laps_completed": int(veh.mTotalLaps),
                    "last_lap_time": float(veh.mLastLapTime),
                    "best_lap_time": float(veh.mBestLapTime),
                    "current_sector": int(veh.mSector) if veh.mSector != 0 else 3,
                    "in_pits": bool(veh.mInPits),
                    "vehicle_class": decode_name(veh.mVehicleClass),
                    "tyre_compound": decode_name(getattr(veh, "mTyreCompound", b"")),
                    "gap_to_player": float(getattr(veh, "mTimeDeltaLeader", 0)),
                    "is_active": bool(getattr(veh, "mIsActive", 1)),
                    "world_x": 0.0,
                    "world_z": 0.0,
                })
            if hasattr(data, "telemetry_arr"):
                for i, rival in enumerate(rivals):
                    if i < len(data.telemetry_arr):
                        t = data.telemetry_arr[i]
                        rival["speed"] = float(t.mSpeed)
                        rival["world_x"] = float(t.mPos.x)
                        rival["world_z"] = float(t.mPos.z)
            d["rivals"] = rivals
            d["num_rivals"] = len(rivals)
        except Exception as e:
            logger.error(f"Error reading LMU shared memory: {e}")
            return {"session_running_time": 0.0}
        return d

    def reinitialize(self) -> bool:
        import subprocess
        try:
            r = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq LMU.exe"],
                capture_output=True, text=True, timeout=5,
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
