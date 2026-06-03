import logging
from typing import Optional

logger = logging.getLogger("vantare.frame_cache")


class FrameCache:
    def __init__(self, reader):
        self._reader = reader
        self._latest: Optional[dict] = None
        self._spotter: Optional[dict] = None
        self._frame_id: int = 0
        self._last_et: float = -1.0

    def read_full(self) -> dict:
        raw = self._reader.get_flat_dict()
        et = raw.get("session_running_time", 0.0)
        if et == self._last_et and self._latest is not None and et > 0:
            return self._latest
        self._last_et = et
        self._merge_rest(raw)
        self._latest = raw
        self._frame_id += 1
        rivals = [
            {
                "id": i,
                "world_x": r.get("world_x", 0),
                "world_z": r.get("world_z", 0),
                "speed": r.get("speed", 0),
                "in_pits": r.get("in_pits", False),
            }
            for i, r in enumerate(raw.get("rivals", []))
        ]
        self._spotter = {
            "world_x": raw.get("world_x", 0),
            "world_z": raw.get("world_z", 0),
            "rotation_yaw": raw.get("rotation_yaw", 0),
            "speed_ms": raw.get("speed_ms", 0),
            "rivals": rivals,
            "session_phase": raw.get("session_phase", 0),
            "in_pits": raw.get("in_pits", False),
            "frame_id": self._frame_id,
        }
        return self._latest

    def get_spotter_frame(self) -> dict:
        self.read_full()  # Always refresh — read_full has dedup built-in
        return self._spotter

    def _merge_rest(self, raw: dict) -> None:
        try:
            from src.services.lmu_api import get_garage_wear
            rest = get_garage_wear()
            if rest:
                if "wearables" in rest:
                    w = rest["wearables"]
                    if "tires" in w and w["tires"]:
                        raw["tyre_wear"] = [float(x) for x in w["tires"]]
                    if "brakes" in w and w["brakes"]:
                        raw["brake_wear"] = [float(x) for x in w["brakes"]]
                    if "body" in w and "aero" in w["body"]:
                        raw["damage_aero"] = float(w["body"]["aero"])
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"REST merge failed: {e}")
