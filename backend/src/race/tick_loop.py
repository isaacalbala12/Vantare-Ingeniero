from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from src.intelligence.spotter_adapter import frame_to_spotter_tick
from src.race.telemetry_hub import TelemetryHub

logger = logging.getLogger("vantare.race_tick")

TICK_INTERVAL_S = 0.05  # 20 Hz


@dataclass
class RaceTickDeps:
    strategy_service: Any
    spotter_service: Any
    crewchief_loop: Any
    intelligence_engine: Any
    telemetry_hub: TelemetryHub


async def run_race_tick_once(deps: RaceTickDeps) -> None:
    strategy = deps.strategy_service
    if strategy is None:
        return

    snapshot = strategy.snapshot_frame()
    if snapshot is None:
        return

    advice_obj = strategy.get_latest_advice()
    advice_dict = advice_obj.model_dump(mode="json") if advice_obj is not None else None

    spotter = deps.spotter_service
    if spotter is not None and getattr(spotter, "enabled", False):
        spotter_tick = frame_to_spotter_tick(snapshot, advice_dict)
        spotter.evaluate_tick(spotter_tick)

    cc_loop = deps.crewchief_loop
    engine = deps.intelligence_engine
    if cc_loop is not None and engine is not None and getattr(engine, "engineer_enabled", False):
        try:
            cc_loop.on_frame(snapshot, now=time.monotonic(), strategy=advice_dict or {})
        except Exception as exc:
            logger.debug("CrewChief on_frame failed: %s", exc)

    now = time.monotonic()
    deps.telemetry_hub.update(snapshot=snapshot, advice=advice_dict)
    deps.telemetry_hub.record_tick_time(now)


async def race_tick_loop(deps: RaceTickDeps) -> None:
    """Global 20 Hz loop — independent of WebSocket clients."""
    while True:
        loop_started = time.monotonic()
        try:
            await run_race_tick_once(deps)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("race_tick_loop error: %s", exc, exc_info=True)
        elapsed = time.monotonic() - loop_started
        await asyncio.sleep(max(0.0, TICK_INTERVAL_S - elapsed))
