#!/usr/bin/env python3
"""Verificación pipeline sesión: practice vs race gating (sin LMU).

Uso desde la raíz del repo:
  python scripts/verify_session_pipeline.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SHARED = ROOT / "shared-telemetry"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(SHARED))

from shared_telemetry.session_kind import (  # noqa: E402
    is_race_session,
    session_kind_from_lmu_int,
)
from src.intelligence.immediate_alert import proactive_event_id  # noqa: E402
from src.intelligence.proactive_monitors import ProactiveMonitorSuite  # noqa: E402
from src.intelligence.triggers import GapClosedTrigger, PitWindowOpenedTrigger  # noqa: E402


def ok(label: str) -> None:
    print(f"  OK  {label}")


def fail(label: str, detail: str) -> None:
    print(f"  FAIL {label}: {detail}")
    sys.exit(1)


def main() -> None:
    print("Verificando pipeline sesión (practice vs race)...")

    if session_kind_from_lmu_int(3) != "practice":
        fail("lmu_map", "Practice3 debe ser practice")
    ok("LMU Practice3 -> practice")

    if session_kind_from_lmu_int(10) != "race":
        fail("lmu_map", "Race1 debe ser race")
    ok("LMU Race1 -> race")

    if is_race_session({"session_type": "practice"}, {}):
        fail("race_check", "practice no debe ser race")
    ok("is_race_session(practice) -> False")

    suite = ProactiveMonitorSuite()
    suite._last_pit_advice_at = 0
    practice_events = suite.evaluate(
        {"lap_number": 5, "standing_position": 1, "competitors": []},
        {"pit_window_open": True},
        {"phase": "PRACTICE"},
    )
    if any(proactive_event_id(e) == "pit_stops" for e in practice_events):
        fail("proactive", "pit_stops en PRACTICE")
    ok("Proactive: sin pit_stops en práctica")

    suite._last_pit_advice_at = 0
    race_events = suite.evaluate(
        {"lap_number": 5, "standing_position": 1, "session_type": "race", "competitors": []},
        {"pit_window_open": True},
        {"phase": "RACE"},
    )
    if not any(proactive_event_id(e) == "pit_stops" for e in race_events):
        fail("proactive", "pit_stops ausente en RACE")
    ok("Proactive: pit_stops en carrera")

    gap = GapClosedTrigger()
    gap._battle_active = False
    if gap.applies(
        {"gap_ahead": 1.0, "gap_behind": 99.0, "in_pits": False, "session_type": "practice"},
        {},
        {"phase": "PRACTICE"},
    ):
        fail("trigger", "GapClosed en practice")
    ok("Trigger GapClosed silenciado en práctica")

    pit = PitWindowOpenedTrigger()
    pit._window_open_active = False
    if pit.applies(
        {"in_pits": False, "session_type": "practice"},
        {"pit_window": {"pit_window_open": True}},
        {"phase": "PRACTICE"},
    ):
        fail("trigger", "PitWindow en practice")
    ok("Trigger PitWindow silenciado en práctica")

    print("\nEjecutando pytest session gating...")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_session_race_gating.py",
            "tests/test_lmu_feedback_fixes.py",
            "-q",
            "--tb=short",
        ],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        fail("pytest", "tests de sesión fallaron")
    ok("pytest session gating")

    shared_result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_session_kind.py", "-q", "--tb=short"],
        cwd=SHARED,
        capture_output=True,
        text=True,
    )
    if shared_result.returncode != 0:
        print(shared_result.stdout)
        print(shared_result.stderr)
        fail("pytest", "test_session_kind falló")
    ok("pytest shared-telemetry session_kind")

    print("\nPipeline sesión: OK")


if __name__ == "__main__":
    main()
