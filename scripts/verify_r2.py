#!/usr/bin/env python3
"""Wave 7 — Verificación automatizada R2 (Tasks 15-23)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / ".omo" / "evidence" / "final-qa-r2"
EVIDENCE.mkdir(parents=True, exist_ok=True)


def run_pytest(paths: list[str]) -> dict:
    cmd = [sys.executable, "-m", "pytest", *paths, "-q", "--tb=no"]
    proc = subprocess.run(cmd, cwd=ROOT / "backend", capture_output=True, text=True)
    passed = proc.returncode == 0
    tail = (proc.stdout or proc.stderr).strip().splitlines()
    summary = tail[-1] if tail else ""
    return {"pass": passed, "summary": summary, "returncode": proc.returncode}


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

    # Task 15 — competitor queries
    def t15_name():
        from shared_strategy.models import CompetitorPace
        from src.intelligence.competitor_queries import query_by_name
        paces = [
            CompetitorPace(
                driver_index=1, driver_name="Sergio Pérez", driver_class="Hypercar",
                standing_position=3, class_position=2, gap_to_player=2.0,
                best_lap=108.0, average_lap=109.0, estimated_stint_length=30,
                num_pit_stops=0, in_pits=False,
            )
        ]
        r = query_by_name("Perez", paces)
        return r.found and "Pérez" in r.driver_name

    def t15_position():
        from shared_strategy.models import CompetitorPace
        from src.intelligence.competitor_queries import query_by_position
        paces = [
            CompetitorPace(
                driver_index=2, driver_name="Kevin Magnussen", driver_class="GT3",
                standing_position=12, class_position=4, gap_to_player=-1.5,
                best_lap=112.0, average_lap=113.0, estimated_stint_length=25,
                num_pit_stops=0, in_pits=False,
            )
        ]
        return query_by_position(12, paces).found

    def t15_tool_defined():
        from src.intelligence.prompt_templates import COMPETITOR_QUERY_TOOL
        return COMPETITOR_QUERY_TOOL["function"]["name"] == "query_competitor"

    scenarios += [
        scenario("task-15-query-by-name", t15_name),
        scenario("task-15-query-by-position", t15_position),
        scenario("task-15-tool-call-defined", t15_tool_defined),
    ]

    # Task 16 — monitoring lifecycle
    def t16_monitor():
        from shared_strategy.competitors import start_monitoring, stop_monitoring, get_monitored
        from shared_strategy.models import CompetitorTrackerState
        st = CompetitorTrackerState()
        st = start_monitoring(st, 5)
        ok = get_monitored(st) == [5]
        st = stop_monitoring(st, 5)
        return ok and get_monitored(st) == []

    scenarios.append(scenario("task-16-monitor-lifecycle", t16_monitor))

    def t16_events():
        from shared_strategy.competitors import evaluate_monitored_events, start_monitoring
        from shared_strategy.models import CompetitorPace, CompetitorTrackerState
        st = start_monitoring(CompetitorTrackerState(), 7)
        p = CompetitorPace(
            driver_index=7, driver_name="R", driver_class="GT3",
            standing_position=3, class_position=1, gap_to_player=1.0,
            best_lap=100, average_lap=101, estimated_stint_length=25,
            num_pit_stops=0, in_pits=False,
        )
        _, st = evaluate_monitored_events([p], st)
        p2 = p.model_copy(update={"in_pits": True})
        ev, _ = evaluate_monitored_events([p2], st)
        return any(e["type"] == "pit_entry" for e in ev)

    scenarios.append(scenario("task-16-monitor-events", t16_events))

    # Task 17 — class filter
    def t17_gt3():
        from shared_strategy.competitors import filter_by_class
        from shared_strategy.models import CompetitorPace
        paces = [
            CompetitorPace(
                driver_index=1, driver_name="A", driver_class="Hypercar",
                standing_position=1, class_position=1, gap_to_player=0,
                best_lap=90, average_lap=91, estimated_stint_length=30,
                num_pit_stops=0, in_pits=False,
            ),
            CompetitorPace(
                driver_index=2, driver_name="B", driver_class="GT3",
                standing_position=5, class_position=2, gap_to_player=3,
                best_lap=100, average_lap=101, estimated_stint_length=25,
                num_pit_stops=0, in_pits=False,
            ),
        ]
        return len(filter_by_class(paces, "GT3")) == 1

    scenarios.append(scenario("task-17-filter-gt3", t17_gt3))

    # Task 18 — track vs classification order
    def t18_orders():
        from shared_strategy.competitors import order_on_track, order_in_classification
        from shared_strategy.models import CompetitorPace
        paces = [
            CompetitorPace(
                driver_index=1, driver_name="A", driver_class="HY",
                standing_position=1, class_position=1, lap_number=10, lap_distance=3000,
                gap_to_player=0, best_lap=90, average_lap=91, estimated_stint_length=30,
                num_pit_stops=0, in_pits=False,
            ),
            CompetitorPace(
                driver_index=2, driver_name="B", driver_class="GT3",
                standing_position=5, class_position=2, lap_number=10, lap_distance=2500,
                gap_to_player=3, best_lap=100, average_lap=101, estimated_stint_length=25,
                num_pit_stops=0, in_pits=False,
            ),
        ]
        on_track = order_on_track(list(paces))
        by_class = order_in_classification(list(paces))
        return on_track[0].driver_name == "A" and by_class[0].standing_position == 1

    scenarios.append(scenario("task-18-track-vs-classification", t18_orders))

    # Task 19 — spa blanchimont
    def t19_spa():
        from src.intelligence.track_spline import get_track_manager
        return get_track_manager().get_nearest_corner("Spa-Francorchamps", 4500) == "Blanchimont"

    scenarios.append(scenario("task-19-spa-blanchimont", t19_spa))

    # Task 20 — sector analysis
    def t20_sectors():
        from shared_strategy.models import SpatialDeltaPair
        from src.intelligence.sector_analysis import analyze_sectors
        last = [SpatialDeltaPair(distance=4500, value=2.0)]
        raw = [SpatialDeltaPair(distance=4500, value=1.5)]
        insights = analyze_sectors(raw, last, "Spa-Francorchamps", 7004.0, threshold=0.05)
        return len(insights) > 0

    scenarios.append(scenario("task-20-sector-analysis", t20_sectors))

    # Task 21 — corner name
    def t21_corner():
        from src.intelligence.corner_names import distance_to_corner_name
        return distance_to_corner_name("spa", 4500) == "Blanchimont"

    scenarios.append(scenario("task-21-corner-name", t21_corner))

    # Task 22 — mqtt disabled path
    def t22_mqtt():
        from src.services.mqtt_service import MqttService
        from src.config import settings
        svc = MqttService()
        return svc.enabled == settings.MQTT_ENABLED

    scenarios.append(scenario("task-22-mqtt-config", t22_mqtt))

    # Task 23 — engine competitor alert path (import check)
    def t23_engine():
        from src.intelligence.engine import IntelligenceEngine
        return hasattr(IntelligenceEngine, "get_competitors_list")

    scenarios.append(scenario("task-23-engine-competitors", t23_engine))

    # Integration R1+R2
    def int_spotter_still_works():
        from src.intelligence.spotter import SpotterService
        svc = SpotterService()
        return hasattr(svc, "evaluate")

    def int_pearls_still_works():
        from src.intelligence.pearls_of_wisdom import PearlsService, PearlType
        return PearlsService().on_event(PearlType.FAST_LAP) is not None

    scenarios += [
        scenario("integration-r1-spotter", int_spotter_still_works),
        scenario("integration-r1-pearls", int_pearls_still_works),
    ]

    pytest_r2 = run_pytest([
        "tests/test_competitor_queries.py",
        "tests/test_competitors_wave5.py",
        "tests/test_track_spline.py",
        "tests/test_sector_analysis.py",
        "tests/test_corner_names.py",
        "tests/test_mqtt_service.py",
        "tests/test_competitor_engine_ws.py",
    ])

    passed = sum(1 for s in scenarios if s["pass"])
    total = len(scenarios)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "release": "R2",
        "wave": 7,
        "scenarios": scenarios,
        "scenarios_pass": f"{passed}/{total}",
        "pytest_r2": pytest_r2,
        "verdict": "APPROVE" if passed == total and pytest_r2["pass"] else "REJECT",
    }

    out = EVIDENCE / "wave7-qa-r2.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["verdict"] == "APPROVE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
