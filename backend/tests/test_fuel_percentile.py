"""Tests fuel percentile."""

from src.persistence.history_store import HistoryStore
from src.intelligence.fuel_percentile import fuel_consumption_percentile, format_fuel_percentile_message


def test_percentile_with_history(tmp_path, monkeypatch):
    monkeypatch.setattr("src.persistence.history_store.SESSION_FILE", tmp_path / "h.json")
    store = HistoryStore(auto_load=False)
    for i, c in enumerate([3.0, 3.2, 3.5, 3.8, 4.0]):
        store.record_lap(lap=i + 1, fuel_used=c, fuel_remaining=50.0, lap_time=90.0)
    pct = fuel_consumption_percentile(store, 3.1)
    assert pct is not None
    assert 0 <= pct <= 100


def test_format_message():
    msg = format_fuel_percentile_message(10.0, 8.0)
    assert "10" in msg
    assert "8" in msg
