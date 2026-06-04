"""
LMU REST API reader (port 6397).
Provides data NOT available in shared memory:
- VirtualEnergy (Hypercars/GT3)
- Per-corner tyre wear, brake wear, suspension damage
- Aero damage
- Weather in proper units (Celsius)
- Pit menu state
"""
import time
import logging
from typing import Optional
from dataclasses import dataclass, field

try:
    import httpx
    _HTTPX = True
except ImportError:
    import requests as _requests
    _HTTPX = False

logger = logging.getLogger("vantare.lmu_rest")
API_BASE = "http://localhost:6397"


@dataclass
class LMURestData:
    current_virtual_energy: float = 0.0
    max_virtual_energy: float = 0.0
    current_battery: float = 0.0
    max_battery: float = 0.0
    tyre_wear: list = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    brake_wear: list = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    suspension_damage: list = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    aero_damage: float = 0.0
    ambient_temp: float = 0.0
    track_temp: float = 0.0
    rain_intensity: float = 0.0
    cloud_coverage: float = 0.0
    place_in_class: int = 0
    place_overall: int = 0
    vehicle_name: str = ""


class LMURestAPI:
    """Reader for LMU REST API data."""

    _last_data: Optional[LMURestData] = None
    _last_fetch_time: float = 0.0
    _fetch_interval: float = 1.0
    _api_enabled: bool = True
    _backoff: float = 1.0
    _backoff_until: float = 0.0

    @classmethod
    def fetch(cls) -> Optional[LMURestData]:
        """Fetch latest data from LMU REST API."""
        now = time.time()

        if now < cls._backoff_until:
            return cls._last_data

        if now - cls._last_fetch_time < cls._fetch_interval:
            return cls._last_data

        cls._last_fetch_time = now
        result = LMURestData()

        try:
            if _HTTPX:
                resp = httpx.get(
                    f"{API_BASE}/rest/garage/UIScreen/RepairAndRefuel",
                    timeout=2.0,
                )
                status = resp.status_code
                data = resp.json() if status == 200 else None
            else:
                resp = _requests.get(
                    f"{API_BASE}/rest/garage/UIScreen/RepairAndRefuel",
                    timeout=2,
                )
                status = resp.status_code
                data = resp.json() if status == 200 else None

            if status != 200 or data is None:
                cls._backoff = min(cls._backoff * 2, 60.0)
                cls._backoff_until = now + cls._backoff
                return cls._last_data

            cls._backoff = 1.0
            cls._backoff_until = 0.0

            # Weather (convert from Kelvin to Celsius if needed)
            if "currentWeather" in data:
                w = data["currentWeather"]
                if w.get("ambientTempKelvin", 0) > 100:
                    result.ambient_temp = w["ambientTempKelvin"] - 273.15
                if w.get("trackTempKelvin", 0) > 100:
                    result.track_temp = w["trackTempKelvin"] - 273.15
                result.rain_intensity = float(w.get("rainIntensity", 0))
                result.cloud_coverage = float(w.get("cloudCoverage", 0))

            # Virtual Energy / Battery / Fuel
            if "fuelInfo" in data:
                f = data["fuelInfo"]
                result.current_virtual_energy = float(f.get("currentVirtualEnergy", 0))
                result.max_virtual_energy = float(f.get("maxVirtualEnergy", 0))
                result.current_battery = float(f.get("currentBattery", 0))
                result.max_battery = float(f.get("maxBattery", 0))

            # Wearables (tyre wear, brake wear, suspension)
            if "wearables" in data:
                w = data["wearables"]
                if "tires" in w and w["tires"]:
                    result.tyre_wear = [float(x) for x in w["tires"]]
                if "brakes" in w and w["brakes"]:
                    result.brake_wear = [float(x) for x in w["brakes"]]
                if "suspension" in w and w["suspension"]:
                    result.suspension_damage = [float(x) for x in w["suspension"]]
                if "body" in w and w["body"]:
                    result.aero_damage = float(w["body"].get("aero", 0))

            # Position
            if "racePosition" in data:
                rp = data["racePosition"]
                result.place_in_class = int(rp.get("placeInClass", 0))
                result.place_overall = int(rp.get("placeOverall", 0))

            # Vehicle name
            if "teamInfo" in data and data["teamInfo"]:
                result.vehicle_name = data["teamInfo"].get("vehicleName", "")

            cls._last_data = result
            return result

        except Exception as e:
            logger.debug(f"REST API unavailable: {e}")
            cls._backoff = min(cls._backoff * 2, 60.0)
            cls._backoff_until = now + cls._backoff
            return cls._last_data


def merge_rest_into_flat(flat: dict, rest: Optional[LMURestData]):
    """Merge REST API data into the flat dict from shared memory.

    REST data OVERRIDES shared memory data where both exist.
    """
    if rest is None:
        return

    # Virtual Energy (CRITICAL for Hypercars)
    if rest.current_virtual_energy > 0:
        flat["virtual_energy"] = rest.current_virtual_energy
        flat["virtual_energy_max"] = rest.max_virtual_energy

    # Battery
    if rest.current_battery > 0:
        flat["battery_percentage"] = rest.current_battery
        flat["battery_max"] = rest.max_battery

    # Tyre wear per corner (more accurate than shared memory)
    if rest.tyre_wear and len(rest.tyre_wear) >= 4:
        flat["tyre_wear"] = rest.tyre_wear

    # Brake wear
    if rest.brake_wear and len(rest.brake_wear) >= 4:
        flat["brake_wear"] = rest.brake_wear

    # Suspension damage
    if rest.suspension_damage and len(rest.suspension_damage) >= 4:
        flat["suspension_damage"] = rest.suspension_damage

    # Aero damage
    if rest.aero_damage > 0:
        flat["damage_aero"] = rest.aero_damage

    # Weather (already Celsius)
    if rest.ambient_temp != 0:
        flat["ambient_temp"] = rest.ambient_temp
    if rest.track_temp != 0:
        flat["track_temp"] = rest.track_temp
    if rest.rain_intensity > 0:
        flat["rain_intensity"] = rest.rain_intensity
    if rest.cloud_coverage > 0:
        flat["cloud_coverage"] = rest.cloud_coverage

    # Position
    if rest.place_in_class > 0:
        flat["place_in_class"] = rest.place_in_class
    if rest.place_overall > 0:
        flat["place_overall"] = rest.place_overall
