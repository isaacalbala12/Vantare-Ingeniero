"""Tests extensiones de competidores (Wave 5 — Tasks 16-18)."""

from shared_strategy.competitors import (
    filter_by_class,
    classify_gap,
    get_nearest_in_class,
    order_on_track,
    order_in_classification,
    start_monitoring,
    stop_monitoring,
    get_monitored,
)
from shared_strategy.models import CompetitorPace, CompetitorTrackerState


def _paces() -> list[CompetitorPace]:
    return [
        CompetitorPace(
            driver_index=1, driver_name="A", driver_class="Hypercar",
            standing_position=1, class_position=1, lap_number=10, lap_distance=3000,
            gap_to_player=0, best_lap=90, average_lap=91, estimated_stint_length=30,
            num_pit_stops=0, in_pits=False,
        ),
        CompetitorPace(
            driver_index=2, driver_name="B", driver_class="GT3",
            standing_position=5, class_position=2, lap_number=10, lap_distance=2500,
            gap_to_player=3.0, best_lap=100, average_lap=101, estimated_stint_length=25,
            num_pit_stops=0, in_pits=False,
        ),
        CompetitorPace(
            driver_index=3, driver_name="C", driver_class="Hypercar",
            standing_position=2, class_position=2, lap_number=9, lap_distance=4500,
            gap_to_player=1.0, best_lap=89, average_lap=90, estimated_stint_length=30,
            num_pit_stops=1, in_pits=True,
        ),
    ]


def test_filter_by_class():
    gt3 = filter_by_class(_paces(), "GT3")
    assert len(gt3) == 1
    assert gt3[0].driver_name == "B"


def test_classify_gap():
    assert classify_gap(2.0) == "close"
    assert classify_gap(10.0) == "mid"
    assert classify_gap(40.0) == "far"


def test_order_on_track_vs_classification():
    paces = _paces()
    on_track = order_on_track(list(paces))
    by_class = order_in_classification(list(paces))
    assert on_track[0].driver_name == "A"
    assert by_class[0].standing_position == 1
    assert on_track[0].track_position == 1
    # C está en boxes pero adelantó en distancia de vuelta anterior
    assert on_track[1].driver_name in ("C", "B")


def test_monitoring_lifecycle():
    state = CompetitorTrackerState()
    state = start_monitoring(state, 5)
    state = start_monitoring(state, 7)
    assert get_monitored(state) == [5, 7]
    state = stop_monitoring(state, 5)
    assert get_monitored(state) == [7]


def test_evaluate_monitored_events_pit_and_gap():
    from shared_strategy.competitors import evaluate_monitored_events, start_monitoring
    from shared_strategy.models import CompetitorPace, CompetitorTrackerState

    state = start_monitoring(CompetitorTrackerState(), 5)
    p1 = CompetitorPace(
        driver_index=5, driver_name="Rival", driver_class="GT3",
        standing_position=4, class_position=2, gap_to_player=2.0,
        best_lap=100, average_lap=101, estimated_stint_length=25,
        num_pit_stops=0, in_pits=False,
    )
    _, state = evaluate_monitored_events([p1], state)
    p2 = p1.model_copy(update={"in_pits": True, "gap_to_player": 5.0, "standing_position": 6})
    events, _ = evaluate_monitored_events([p2], state)
    types = {e["type"] for e in events}
    assert "pit_entry" in types
    assert "gap_change" in types
