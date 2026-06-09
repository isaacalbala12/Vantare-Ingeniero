from src.intelligence.crewchief_events.frame_builder import build_frame_context
from src.intelligence.crewchief_events.game_state import CrewChiefGameStateLoop
from unittest.mock import MagicMock


def test_build_frame_context_exposes_session_strategy_and_positions():
    previous = {
        "standing_position": 4,
        "game_phase": 6,
        "yellow_flag_state": 0,
    }
    current = {
        "standing_position": 3,
        "game_phase": 6,
        "session_type_int": 10,
        "on_manual_formation_lap": False,
        "session_time_left": 3600.0,
        "yellow_flag_state": 1,
        "condition_wetness": 0.2,
        "start_standing_position": 5,
    }
    strategy = {"pit_window_open": True}

    ctx = build_frame_context(
        previous=previous,
        current=current,
        strategy=strategy,
        now_monotonic=42.0,
    )

    assert ctx.previous_position == 4
    assert ctx.current_position == 3
    assert ctx.strategy["pit_window_open"] is True
    assert ctx.session["session_type_int"] == 10
    assert ctx.session["yellow_flag_state"] == 1
    assert ctx.session["start_standing_position"] == 5
    assert ctx.now_monotonic == 42.0


def test_game_state_loop_captures_start_standing_position_on_first_race_tick():
    engine = MagicMock()
    engine.crewchief_suite = MagicMock()
    loop = CrewChiefGameStateLoop(engine=engine)

    loop.on_frame(
        {"session_type_int": 10, "standing_position": 7, "lap_number": 1},
        now=1.0,
    )
    loop.on_frame(
        {"session_type_int": 10, "standing_position": 6, "lap_number": 1},
        now=1.05,
    )

    first_ctx = engine.crewchief_suite.evaluate.call_args_list[0][0][0]
    second_ctx = engine.crewchief_suite.evaluate.call_args_list[1][0][0]

    assert first_ctx.current["start_standing_position"] == 7
    assert second_ctx.current["start_standing_position"] == 7
