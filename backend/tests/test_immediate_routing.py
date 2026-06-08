"""F1 — routing ImmediateAlert vs commentary batch."""

import pytest

from src.intelligence.engine import IntelligenceEngine
from src.intelligence.immediate_alert import ImmediateAlert
from src.models.messages import AlertMessage, CommentaryEndMessage


@pytest.mark.asyncio
async def test_race_start_goes_immediate_not_batch():
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    eng.apply_runtime_config({"verbosityLevel": "normal"})
    await eng.evaluate_cycle(
        {"lap_number": 1, "standing_position": 5},
        {},
        {"phase": "RACE"},
    )
    alerts = [m for m in sent if isinstance(m, AlertMessage)]
    assert any("Salida" in a.message or "vamos" in a.message.lower() for a in alerts)
    commentary = [m for m in sent if isinstance(m, CommentaryEndMessage)]
    assert not any("Salida" in c.full_text for c in commentary)


@pytest.mark.asyncio
async def test_position_change_goes_immediate_not_batch():
    from src.intelligence.crewchief_events.game_state import CrewChiefGameStateLoop
    from src.intelligence.crewchief_events.modules import PositionEvent
    from src.intelligence.crewchief_events.suite import CrewChiefEventSuite

    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    eng.apply_runtime_config({"verbosityLevel": "normal"})
    eng.crewchief_suite = CrewChiefEventSuite([PositionEvent()], engine=eng)
    loop = CrewChiefGameStateLoop(engine=eng)

    base = {"lap_number": 2, "session_type_int": 10, "session_type": "race"}
    loop.on_frame({**base, "standing_position": 8}, now=1.0)
    loop.on_frame({**base, "standing_position": 6}, now=2.0)

    alerts = [m for m in sent if isinstance(m, AlertMessage) and "P6" in m.message]
    assert alerts
    msg = await eng.commentary.flush()
    assert msg is None or "P6" not in msg.full_text


def test_immediate_alert_dataclass():
    alert = ImmediateAlert("race_start", "Go", "HIGH", "race")
    assert alert.event_id == "race_start"
