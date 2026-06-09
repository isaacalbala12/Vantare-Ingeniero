from __future__ import annotations

import os
import sys

from src.config import settings


def is_windows() -> bool:
    return sys.platform == "win32"


def native_telemetry_enabled() -> bool:
    if not is_windows():
        return False
    env = os.getenv("VANTARE_NATIVE_TELEMETRY")
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes")
    return bool(settings.NATIVE_TELEMETRY)
