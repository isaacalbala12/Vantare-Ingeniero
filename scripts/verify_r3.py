#!/usr/bin/env python3
"""Verificación automatizada R3 (Tasks 24-32) + integración cross-release."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / ".omo" / "evidence" / "final-qa-r3"
EVIDENCE.mkdir(parents=True, exist_ok=True)


def run_pytest(paths: list[str], cwd: Path | None = None) -> dict:
    cmd = [sys.executable, "-m", "pytest", *paths, "-q", "--tb=no", "--timeout=60"]
    proc = subprocess.run(cmd, cwd=cwd or (ROOT / "backend"), capture_output=True, text=True)
    tail = (proc.stdout or proc.stderr).strip().splitlines()
    return {"pass": proc.returncode == 0, "summary": tail[-1] if tail else "", "returncode": proc.returncode}


def scenario(name: str, fn) -> dict:
    try:
        ok = bool(fn())
        return {"name": name, "pass": ok}
    except Exception as e:
        return {"name": name, "pass": False, "error": str(e)}


def main() -> int:
    sys.path.insert(0, str(ROOT / "backend"))
    sys.path.insert(0, str(ROOT / "shared-strategy" / "src"))

    scenarios: list[dict] = []

    # Task 24 — FlagsMonitor
    def t24_yellow():
        from src.intelligence.flags_monitor import detect_flag_transitions, snapshot_from_telemetry
        prev = snapshot_from_telemetry({"yellow_flag_active": False})
        curr = snapshot_from_telemetry({"yellow_flag_active": True})
        return len(detect_flag_transitions(prev, curr)) == 1

    def t24_replaces_safetycar():
        from src.intelligence.triggers import FlagsMonitorTrigger, SafetyCarTrigger
        t = FlagsMonitorTrigger()
        tele = {"safety_car_active": True, "full_course_yellow_active": False}
        return t.condition(tele, {}, {}) and SafetyCarTrigger is FlagsMonitorTrigger

    scenarios += [
        scenario("task-24-yellow-flag", t24_yellow),
        scenario("task-24-flags-monitor-trigger", t24_replaces_safetycar),
    ]

    # Task 25 — Multiclass warnings
    def t25_hypercar():
        from src.intelligence.triggers import MulticlassWarningTrigger
        t = MulticlassWarningTrigger()
        tele = {"in_pits": False, "player_class": "GT3"}
        strat = {"competitors": [{"driver_class": "Hypercar", "gap_to_player": -1.5, "in_pits": False}]}
        return t.condition(tele, strat, {})

    scenarios.append(scenario("task-25-multiclass-warning", t25_hypercar))

    # Task 26 — Driver swap
    def t26_swap():
        from src.intelligence.triggers import DriverSwapTrigger
        t = DriverSwapTrigger()
        tele = {"driver_name": "Alonso"}
        t.condition(tele, {}, {})
        tele["driver_name"] = "Hamilton"
        return t.condition(tele, {}, {})

    scenarios.append(scenario("task-26-driver-swap", t26_swap))

    # Task 27 — Penalties
    def t27_penalty():
        from src.intelligence.triggers import PenaltyMonitorTrigger
        t = PenaltyMonitorTrigger()
        t.condition({"num_penalties": 0}, {}, {})
        return t.condition({"num_penalties": 1}, {}, {})

    scenarios.append(scenario("task-27-penalty-monitor", t27_penalty))

    # Task 28 — Push now + session end
    def t28_push():
        from src.intelligence.triggers import PushNowTrigger, SessionEndTrigger
        push = PushNowTrigger()
        tele = {"in_pits": False, "session_type": "race", "session_laps_left": 2}
        end = SessionEndTrigger()
        tele_end = {"lap_number": 10, "session_laps_left": 0.5, "standing_position": 2, "lap_time_best": 100.0}
        return push.condition(tele, {}, {}) and end.condition(tele_end, {}, {})

    scenarios.append(scenario("task-28-push-and-session-end", t28_push))

    # Task 29 — Profiles
    def t29_profiles(tmp_dir: Path):
        from src.persistence.profile_store import ProfileStore
        import src.persistence.profile_store as ps_mod
        ps_mod.PROFILES_DIR = str(tmp_dir)
        store = ProfileStore()
        store.save_profile("endurance", {"serverPort": 8010})
        return "endurance" in store.list_profiles() and store.load_profile("endurance")["serverPort"] == 8010

    with tempfile.TemporaryDirectory() as td:
        scenarios.append(scenario("task-29-profile-store", lambda: t29_profiles(Path(td))))

    # Task 30 — Auto-update
    def t30_version():
        from src.version import APP_VERSION
        from src.services.update_service import is_newer_version, parse_version
        return APP_VERSION == "0.1.0" and is_newer_version("0.2.0", "0.1.0") and parse_version("v1.0.0") == (1, 0, 0)

    scenarios.append(scenario("task-30-version-check", t30_version))

    # Task 31 — LMU dummy
    def t31_dummy():
        from fastapi.testclient import TestClient
        from src.debug.lmu_dummy_server import create_app
        c = TestClient(create_app())
        w = c.get("/rest/sessions/weather")
        s = c.get("/rest/strategy/usage")
        g = c.get("/rest/garage/UIScreen/RepairAndRefuel")
        return w.status_code == 200 and s.status_code == 200 and g.status_code == 200

    scenarios.append(scenario("task-31-lmu-dummy-server", t31_dummy))

    # Task 32 — Traces
    def t32_traces(tmp_dir: Path):
        import asyncio
        import src.persistence.trace_store as ts_mod
        from src.persistence.trace_store import TraceStore

        ts_mod.TRACES_DIR = str(tmp_dir)
        store = TraceStore()
        tid = store.start_recording("qa-trace")
        store.append_frame({"lap_number": 1, "speed": 50.0})
        store.stop_recording()

        received: list[dict] = []

        async def cb(frame):
            received.append(frame)

        async def _run():
            count = await store.playback(tid, cb, speed=10.0)
            return count == 1 and received[0]["lap_number"] == 1

        return asyncio.run(_run())

    with tempfile.TemporaryDirectory() as td:
        scenarios.append(scenario("task-32-trace-playback", lambda: t32_traces(Path(td))))

    # Cross-release integration
    def x_monitor_tool():
        from src.intelligence.engine import IntelligenceEngine
        from unittest.mock import MagicMock
        from shared_strategy.models import CompetitorTrackerState

        eng = IntelligenceEngine(broadcaster=MagicMock(), llm_client=MagicMock())
        svc = MagicMock()
        svc.state.competitors = CompetitorTrackerState()
        eng.strategy_service = svc
        msg = eng.apply_monitor_competitor("start", 3)
        return "Monitorizando" in msg and 3 in svc.state.competitors.monitored

    def x_spotter_flags():
        from src.intelligence.spotter import SpotterService
        from src.intelligence.triggers import FlagsMonitorTrigger

        spotter = SpotterService()
        flags = FlagsMonitorTrigger()
        tick = {"session_type": "race", "in_pits": False, "player_class": "GT3", "competitors": []}
        return spotter.enabled and not flags.condition({"safety_car_active": False}, {}, {})

    scenarios += [
        scenario("integration-monitor-competitor", x_monitor_tool),
        scenario("integration-spotter-flags-coexist", x_spotter_flags),
    ]

    pytest_r3 = run_pytest(
        [
            "tests/test_flags_monitor.py",
            "tests/test_wave8_events.py",
            "tests/test_profile_store.py",
            "tests/test_trace_store.py",
            "tests/test_update_service.py",
            "tests/test_lmu_dummy_server.py",
            "tests/test_wave9_routers.py",
            "tests/test_monitor_competitor_tool.py",
        ]
    )
    pytest_full = run_pytest(["--ignore=benchmarks"])
    pytest_strategy = run_pytest(["tests/"], cwd=ROOT / "shared-strategy")

    npm_proc = subprocess.run(
        ["npm", "test"],
        cwd=ROOT / "frontend",
        capture_output=True,
        text=True,
        shell=True,
    )
    npm_tail = (npm_proc.stdout or npm_proc.stderr).strip().splitlines()
    npm_ok = npm_proc.returncode == 0

    scenario_pass = sum(1 for s in scenarios if s["pass"])
    scenario_total = len(scenarios)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "release": "R3",
        "tasks": "24-32",
        "scenarios": scenarios,
        "scenarios_pass": scenario_pass,
        "scenarios_total": scenario_total,
        "pytest_r3_subset": pytest_r3,
        "pytest_backend_full": pytest_full,
        "pytest_shared_strategy": pytest_strategy,
        "frontend_vitest": {"pass": npm_ok, "summary": npm_tail[-3:] if npm_tail else []},
        "verdict": "APPROVE"
        if scenario_pass == scenario_total
        and pytest_r3["pass"]
        and pytest_full["pass"]
        and pytest_strategy["pass"]
        and npm_ok
        else "REJECT",
    }

    out_json = EVIDENCE / "wave10-r3-verification.json"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"R3 scenarios: {scenario_pass}/{scenario_total}")
    for s in scenarios:
        mark = "PASS" if s["pass"] else "FAIL"
        print(f"  [{mark}] {s['name']}")
    print(f"pytest R3 subset: {pytest_r3['summary']}")
    print(f"pytest backend:   {pytest_full['summary']}")
    print(f"pytest strategy:  {pytest_strategy['summary']}")
    print(f"frontend vitest:  {'PASS' if npm_ok else 'FAIL'}")
    print(f"VERDICT: {report['verdict']}")
    print(f"Evidence: {out_json}")

    return 0 if report["verdict"] == "APPROVE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
