from src.intelligence.crewchief_events.modules.position import PositionEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext
from src.intelligence.spotter_grid import compute_grid_side


def test_grid_side_left_when_neighbor_is_on_negative_lateral():
    competitors = [
        {"driver_index": 1, "world_x": -2.0, "world_z": 0.0},
        {"driver_index": 2, "world_x": 2.0, "world_z": 0.0},
    ]
    side = compute_grid_side(
        competitors,
        player_index=0,
        player_forward=(0.0, 1.0),
        adjacent_indices=[1, 2],
    )
    assert side == "both"


def test_position_module_announces_grid_side_once():
    module = PositionEvent()
    ctx = CrewChiefFrameContext(
        previous={"lap_number": 0, "standing_position": 5, "session_type_int": 10},
        current={
            "lap_number": 1,
            "standing_position": 5,
            "session_type_int": 10,
            "grid_side": "left",
        },
        strategy={},
        session={"phase": "race", "session_type_int": 10},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "race_start_grid_side" for m in messages)
