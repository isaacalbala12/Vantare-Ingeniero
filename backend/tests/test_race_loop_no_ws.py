import asyncio
from unittest.mock import MagicMock

import pytest

from src.race.telemetry_hub import TelemetryHub
from src.race.tick_loop import RaceTickDeps, race_tick_loop


@pytest.mark.asyncio
async def test_race_loop_increments_hub_without_websocket():
    hub = TelemetryHub()
    strategy = MagicMock()
    strategy.snapshot_frame.side_effect = [{"lap": i} for i in range(10)]
    strategy.get_latest_advice.return_value = None
    spotter = MagicMock()
    spotter.enabled = True
    cc = MagicMock()
    engine = MagicMock()
    engine.engineer_enabled = True

    deps = RaceTickDeps(strategy, spotter, cc, engine, hub)
    task = asyncio.create_task(race_tick_loop(deps))
    await asyncio.sleep(0.25)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert hub.tick_count >= 3
    assert cc.on_frame.call_count >= 3
