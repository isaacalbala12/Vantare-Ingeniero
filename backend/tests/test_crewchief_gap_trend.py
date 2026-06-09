from src.intelligence.crewchief_events.gap_trend import GapTrend, classify_gap_trend


def test_increasing_when_samples_rise():
    samples = [2.0, 2.3, 2.6]
    assert classify_gap_trend(samples) == GapTrend.INCREASING


def test_decreasing_when_samples_fall():
    samples = [2.0, 1.7, 1.4]
    assert classify_gap_trend(samples) == GapTrend.DECREASING


def test_holding_when_samples_flat():
    samples = [2.0, 2.05, 1.98]
    assert classify_gap_trend(samples) == GapTrend.HOLDING


def test_close_when_last_sample_under_threshold():
    samples = [1.5, 1.2, 0.9]
    assert classify_gap_trend(samples, close_threshold_s=1.0) == GapTrend.CLOSE


def test_unknown_with_fewer_than_three_samples():
    assert classify_gap_trend([2.0, 2.5]) is None
