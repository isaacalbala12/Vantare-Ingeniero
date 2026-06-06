"""Tests integración competidor en engine (Wave 6 — Task 23)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from shared_strategy.models import CompetitorPace


@pytest.mark.asyncio
async def test_handle_pilot_question_emits_competitor_alert():
    from src.intelligence.engine import IntelligenceEngine

    broadcaster = MagicMock()
    strategy = MagicMock()
    advice = MagicMock()
    advice.competitors = [
        CompetitorPace(
            driver_index=1,
            driver_name="Sergio Pérez",
            driver_class="Hypercar",
            standing_position=3,
            class_position=2,
            gap_to_player=2.0,
            best_lap=108.0,
            average_lap=109.0,
            estimated_stint_length=30,
            num_pit_stops=0,
            in_pits=False,
        )
    ]
    strategy.get_latest_advice.return_value = advice

    engine = IntelligenceEngine(
        broadcaster=broadcaster,
        strategy_service=strategy,
        llm_client=MagicMock(),
    )

    with patch.object(engine, "evaluate_cycle", new=AsyncMock()):
        await engine.handle_pilot_question("¿Qué tal va Pérez?")

    competitor_alerts = [
        c for c in broadcaster.send.call_args_list
        if getattr(c[0][0], "category", None) == "competitor"
    ]
    assert len(competitor_alerts) >= 1
