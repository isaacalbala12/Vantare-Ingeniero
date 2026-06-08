#!/usr/bin/env python3
"""Smoke test MQTT opt-in (A8). Requiere broker local opcional."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.services.mqtt_service import MqttService  # noqa: E402


async def _run() -> int:
    svc = MqttService()
    if not svc.enabled:
        print("MQTT disabled in settings — enable MQTT_ENABLED to test publish.")
        return 0
    ok = svc._ensure_client()
    if not ok:
        print("MQTT broker not reachable — skip (non-fatal for CI).")
        return 0
    sample = {"lap_number": 1, "speed": 120, "standing_position": 5}
    await svc.publish_telemetry(sample)
    print("MQTT publish_telemetry: OK")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
