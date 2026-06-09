from src.intelligence.crewchief_events.modules.frozen_order import FrozenOrderEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_frozen_order_start_edge():
    module = FrozenOrderEvent()
    messages = module.evaluate(
        CrewChiefFrameContext(
            previous={"frozen_order_active": False, "session_type_int": 10},
            current={"frozen_order_active": True, "session_type_int": 10},
            strategy={},
            session={"phase": "race", "enable_frozen_order_messages": True},
            now_monotonic=1.0,
        )
    )
    assert any(m.event_id == "frozen_order" for m in messages)


def test_frozen_order_waits_for_stable_instruction():
    module = FrozenOrderEvent(stability_seconds=2.0)
    first = CrewChiefFrameContext(
        previous={"frozen_order_active": True, "session_type_int": 10},
        current={
            "frozen_order_active": True,
            "frozen_order_message": "Mantén la fila izquierda",
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "enable_frozen_order_messages": True},
        now_monotonic=1.0,
    )
    second = CrewChiefFrameContext(
        previous=first.current,
        current=first.current,
        strategy={},
        session={"phase": "race", "enable_frozen_order_messages": True},
        now_monotonic=3.1,
    )
    assert module.evaluate(first) == []
    messages = module.evaluate(second)
    assert messages[0].event_id == "frozen_order_instruction"
