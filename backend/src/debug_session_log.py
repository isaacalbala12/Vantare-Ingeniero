"""NDJSON debug logs for agent session 69c028 (TTS pipeline audit)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_LOG_PATH = Path(__file__).resolve().parents[2] / "debug-69c028.log"
_SESSION = "69c028"


def debug_session_log(
    location: str,
    message: str,
    data: dict[str, Any] | None = None,
    *,
    hypothesis_id: str = "",
    run_id: str = "pre-fix",
) -> None:
    try:
        entry = {
            "sessionId": _SESSION,
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data or {},
            "hypothesisId": hypothesis_id,
            "runId": run_id,
        }
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
