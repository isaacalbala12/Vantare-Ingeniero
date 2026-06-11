import asyncio
from unittest.mock import MagicMock

import pytest

from src.race.telemetry_hub import TelemetryHub
from src.race.tick_loop import RaceTickDeps, run_race_tick_once


@pytest.mark.asyncio
async def test_run_race_tick_once_evaluates_spotter_and_cc():
    hub = TelemetryHub()
    spotter = MagicMock()
    spotter.enabled = True
    cc_loop = MagicMock()
    engine = MagicMock()
    engine.engineer_enabled = True

    strategy = MagicMock()
    strategy.snapshot_frame.return_value = {"lap": 5, "competitors": []}
    advice = MagicMock()
    advice.model_dump.return_value = {"fuel_laps": 3}
    strategy.get_latest_advice.return_value = advice

    deps = RaceTickDeps(
        strategy_service=strategy,
        spotter_service=spotter,
        crewchief_loop=cc_loop,
        intelligence_engine=engine,
        telemetry_hub=hub,
    )

    await run_race_tick_once(deps)

    assert spotter.evaluate_tick.called
    cc_loop.on_frame.assert_called_once()
    snap, adv = hub.get_latest()
    assert snap["lap"] == 5
    assert adv["fuel_laps"] == 3


@pytest.mark.asyncio
async def test_run_race_tick_once_skips_when_no_snapshot():
    hub = TelemetryHub()
    spotter = MagicMock()
    spotter.enabled = True
    strategy = MagicMock()
    strategy.snapshot_frame.return_value = None

    deps = RaceTickDeps(
        strategy_service=strategy,
        spotter_service=spotter,
        crewchief_loop=MagicMock(),
        intelligence_engine=MagicMock(),
        telemetry_hub=hub,
    )

    await run_race_tick_once(deps)
    spotter.evaluate_tick.assert_not_called()
