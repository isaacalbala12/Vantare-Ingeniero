#!/usr/bin/env python3
"""Smoke gate: engine cycle + formatter + config apply without LMU."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


async def smoke() -> None:
    from src.intelligence.engine import IntelligenceEngine

    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    assert eng.runtime_config_snapshot().get("enableCommentaryBatch") is False
    eng.apply_runtime_config({"personalityProfileId": "standard", "verbosityLevel": "normal"})
    await eng.evaluate_cycle(
        {"lap_number": 1, "standing_position": 3},
        {},
        {"phase": "RACE"},
    )
    msg = await eng.commentary.flush()
    assert msg is None or msg.event == "commentary_end"


def main() -> None:
    backend = ROOT / "backend"
    asyncio.run(smoke())
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_crewchief_no_legacy_emitters.py",
            "tests/test_replay_trace.py",
            "tests/test_crewchief_wave7_cutover.py",
            "tests/test_no_sidecar_endpoint.py",
            "tests/test_native_telemetry.py",
            "tests/test_native_telemetry_frame_source.py",
            "-q",
        ],
        cwd=str(backend),
    )
    spotter_script = ROOT / "scripts" / "verify_spotter_pipeline.py"
    if spotter_script.is_file():
        subprocess.run([sys.executable, str(spotter_script)], check=True)
    print("=== Alpha parity smoke OK ===")


if __name__ == "__main__":
    main()
