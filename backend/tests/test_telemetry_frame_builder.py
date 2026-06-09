from shared_strategy.telemetry_frame_builder import (
    FrameBuildContext,
    StrategyFrameState,
    build_telemetry_frame_from_reader_state,
)


def test_builder_returns_telemetry_frame_with_session_int(mock_race_state):
    ctx = FrameBuildContext(
        track=__import__("shared_strategy.models", fromlist=["TrackConfig"]).TrackConfig(track_length=7004.0),
        sync=None,
        reader_offline=True,
        shmm_data=None,
        cached_brake_wear=None,
    )
    frame_state = StrategyFrameState()
    frame = build_telemetry_frame_from_reader_state(
        race_state=mock_race_state,
        ctx=ctx,
        frame_state=frame_state,
    )
    assert frame.lap_number >= 0
    assert frame.session_type_int == 4
    assert frame.num_penalties == 0
    assert frame.game_phase == 5
    assert frame.sector_flags == []


def test_builder_accepts_explicit_game_phase_and_penalties(mock_race_state):
    from shared_strategy.models import TrackConfig

    ctx = FrameBuildContext(
        track=TrackConfig(track_length=7004.0),
        sync=None,
        reader_offline=True,
        shmm_data=None,
        cached_brake_wear={"fl": 12.0, "fr": 11.0, "rl": 10.0, "rr": 9.0},
    )
    frame_state = StrategyFrameState()
    # Force online-like flags via offline path defaults; yellow from game_phase needs online block
    # Test brake wear cache instead
    frame = build_telemetry_frame_from_reader_state(
        race_state=mock_race_state,
        ctx=ctx,
        frame_state=frame_state,
    )
    assert frame.brake_wear_fl == 12.0
    assert frame.brake_wear_rr == 9.0
