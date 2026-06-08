from src.intelligence.crewchief_events.base import CrewChiefEventModule
from src.intelligence.crewchief_events.game_state import CrewChiefGameStateLoop
from src.intelligence.crewchief_events.suite import CrewChiefEventSuite
from src.intelligence.crewchief_events.types import (
    CrewChiefChannel,
    CrewChiefFrameContext,
    CrewChiefMessage,
    CrewChiefPriority,
)


class PositionGainModule(CrewChiefEventModule):
    event_name = "position_gain"

    def evaluate(self, ctx: CrewChiefFrameContext):
        if ctx.previous_position is None or ctx.current_position is None:
            return []
        if ctx.current_position < ctx.previous_position:
            return [
                CrewChiefMessage(
                    event_id="position_gain",
                    text=f"Subiste a P{ctx.current_position}.",
                    priority=CrewChiefPriority.IMPORTANT,
                    channel=CrewChiefChannel.ENGINEER,
                )
            ]
        return []


def _race_ctx(*, previous: dict, current: dict, now: float) -> CrewChiefFrameContext:
    return CrewChiefFrameContext(
        previous=previous,
        current=current,
        strategy={},
        session={"phase": "RACE", "session_type_int": 10},
        now_monotonic=now,
    )


def test_suite_passes_previous_frame_to_modules():
    suite = CrewChiefEventSuite([PositionGainModule()])
    first = suite.evaluate(
        _race_ctx(previous={}, current={"standing_position": 4}, now=1.0),
    )
    second = suite.evaluate(
        _race_ctx(
            previous={"standing_position": 4},
            current={"standing_position": 3},
            now=2.0,
        ),
    )

    assert first == []
    assert [m.text for m in second] == ["Subiste a P3."]


def test_suite_clear_state_resets_module_state():
    suite = CrewChiefEventSuite([PositionGainModule()])
    suite.evaluate(
        _race_ctx(previous={}, current={"standing_position": 4}, now=1.0),
    )
    suite.clear_state()
    messages = suite.evaluate(
        _race_ctx(previous={}, current={"standing_position": 3}, now=2.0),
    )

    assert messages == []


import pytest

from src.intelligence.engine import IntelligenceEngine
from src.models.messages import AlertMessage, CommentaryEndMessage


@pytest.mark.asyncio
async def test_evaluate_cycle_blocks_cc_owned_position_commentary():
    """Legacy proactive must not batch position_change once CC owns it."""
    sent = []
    engine = IntelligenceEngine(broadcast_callback=sent.append)
    engine.apply_runtime_config({"verbosityLevel": "normal"})
    engine._last_standing_position = 4

    await engine.evaluate_cycle(
        {"lap_number": 2, "standing_position": 3, "session_type": "race"},
        {},
        {"phase": "RACE"},
    )

    pending_ids = [evt.event_id for evt in engine.commentary._pending]
    assert "position_change" not in pending_ids
    commentary = [m for m in sent if isinstance(m, CommentaryEndMessage)]
    assert not any("P3" in c.full_text for c in commentary)


@pytest.mark.asyncio
async def test_evaluate_cycle_blocks_cc_owned_penalty_immediate():
    """Penalty alerts belong to CC module path, not legacy ImmediateAlert."""
    sent = []
    engine = IntelligenceEngine(broadcast_callback=sent.append)
    engine.apply_runtime_config({"verbosityLevel": "normal"})

    from src.intelligence.immediate_alert import ImmediateAlert

    def fake_evaluate(*args, **kwargs):
        return [
            ImmediateAlert(
                event_id="penalty_new",
                message="Penalización.",
                priority="HIGH",
                category="penalty",
            )
        ]

    engine.proactive_monitors.evaluate = fake_evaluate

    await engine.evaluate_cycle(
        {"lap_number": 2, "standing_position": 5},
        {},
        {"phase": "RACE"},
    )

    alerts = [m for m in sent if isinstance(m, AlertMessage)]
    assert not any("Penalización" in a.message for a in alerts)


def test_crewchief_position_via_game_state_loop_not_commentary_batch():
    from src.intelligence.engine import IntelligenceEngine
    from src.intelligence.crewchief_events.modules import PositionEvent
    from src.models.messages import AlertMessage, CommentaryEndMessage

    sent = []
    engine = IntelligenceEngine(broadcast_callback=sent.append)
    engine.crewchief_suite = CrewChiefEventSuite([PositionEvent()], engine=engine)
    loop = CrewChiefGameStateLoop(engine=engine)

    base = {"lap_number": 2, "session_type_int": 10, "session_type": "race"}
    loop.on_frame({**base, "standing_position": 8}, now=1.0)
    loop.on_frame({**base, "standing_position": 6}, now=8.0)

    alerts = [m for m in sent if isinstance(m, AlertMessage)]
    assert any("P6" in a.message for a in alerts)
    assert not any(
        isinstance(m, CommentaryEndMessage) and "P6" in m.full_text for m in sent
    )
