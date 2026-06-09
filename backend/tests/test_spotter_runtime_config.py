"""Tests apply_runtime_config en SpotterService."""

from src.intelligence.spotter import SpotterService


def test_spotter_apply_runtime_config_updates_delays():
    spotter = SpotterService(broadcast_callback=lambda m: None)
    spotter.apply_runtime_config({
        "spotterClearDelayS": 2.5,
        "spotterOverlapDelayS": 3.0,
        "spotterGapFrequencyS": 45.0,
        "spotterCarLengthM": 5.2,
    })
    assert spotter._proximity_state.clear_delay_s == 2.5
    assert spotter._proximity_state.overlap_delay_s == 3.0
    assert spotter._gap_frequency_s == 45.0
    assert spotter._car_length_m == 5.2


def test_spotter_apply_runtime_config_personality_phrases():
    from src.intelligence.spotter_geometry import LateralProximity
    from src.intelligence.spotter_state import SideState

    spotter = SpotterService(broadcast_callback=lambda m: None)
    spotter.apply_runtime_config({"personalityProfileId": "aggressive"})
    sm = spotter._proximity_state
    sm._left_state = SideState.CAR_PRESENT
    sm._left_present_since = 0.0
    sm.still_there_enabled = False
    hit = LateralProximity(
        side="izquierda",
        driver_index=1,
        driver_class="GT3",
        driver_name="Rival",
        lateral_m=1.0,
        distance_m=2.0,
        closing_mps=0.0,
    )
    sm._left_hit = hit
    transitions = sm._maybe_hold_or_closing("izquierda", hit, sm.overlap_delay_s + 1.0)
    assert transitions
    assert "Aguanta" in transitions[0].message
