from src.intelligence.spotter_geometry import LateralProximity
from src.intelligence.spotter_state import SpotterStateMachine


def test_line_astern_not_three_wide_when_lateral_spread_below_car_width():
    sm = SpotterStateMachine(use_3wide_left_right=True, car_width_m=2.0)
    hits = [
        LateralProximity(
            driver_index=1,
            driver_class="GT3",
            driver_name="A",
            lateral_m=0.3,
            side="izquierda",
            distance_m=1.0,
        ),
        LateralProximity(
            driver_index=2,
            driver_class="GT3",
            driver_name="B",
            lateral_m=0.4,
            side="derecha",
            distance_m=1.0,
        ),
    ]
    transitions = sm.update(
        hits,
        player_class="GT3",
        threshold_m=3.0,
        now=1.0,
    )
    assert not any(t.is_three_wide for t in transitions)
