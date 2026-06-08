import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.intelligence.crewchief_events.game_state import CrewChiefGameStateLoop


def test_suite_runs_on_every_telemetry_tick_not_evaluate_cycle():
    engine = MagicMock()
    engine.crewchief_suite = MagicMock()
    loop = CrewChiefGameStateLoop(engine=engine)
    frame_a = {"lap_number": 1, "session_type_int": 3}
    frame_b = {"lap_number": 1, "session_type_int": 3, "speed": 42.0}

    loop.on_frame(frame_a, now=1.0)
    loop.on_frame(frame_b, now=1.05)

    assert engine.crewchief_suite.evaluate.call_count == 2
    engine.evaluate_cycle.assert_not_called()


@pytest.mark.asyncio
async def test_evaluate_cycle_does_not_invoke_crewchief_suite():
    from src.intelligence.engine import IntelligenceEngine

    engine = IntelligenceEngine(broadcast_callback=lambda _msg: None)
    engine.crewchief_suite = MagicMock()

    with patch.object(engine, "_run_proactive_monitors", new=AsyncMock()):
        with patch.object(engine, "_maybe_emit_pearls"):
            await engine.evaluate_cycle(
                {"lap_number": 1, "session_type_int": 10},
                {},
            )

    engine.crewchief_suite.evaluate.assert_not_called()
