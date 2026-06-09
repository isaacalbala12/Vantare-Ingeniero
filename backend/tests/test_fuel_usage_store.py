from src.persistence.fuel_usage_store import FuelUsageStore


def test_record_and_get_samples(monkeypatch):
    monkeypatch.setattr("src.persistence.fuel_usage_store.random.random", lambda: 0.0)
    store = FuelUsageStore(auto_load=False)
    store.record_sample("LMU", "GT3", "Spa", 2.5)
    store.record_sample("LMU", "GT3", "Spa", 2.6)
    samples = store.get_samples("LMU", "GT3", "Spa")
    assert len(samples) == 2
    assert samples[0]["consumption_l"] == 2.5


def test_max_five_samples(monkeypatch):
    monkeypatch.setattr("src.persistence.fuel_usage_store.random.random", lambda: 0.0)
    store = FuelUsageStore(auto_load=False)
    for i in range(7):
        store.record_sample("LMU", "Car", "Track", float(i + 1))
    samples = store.get_samples("LMU", "Car", "Track")
    assert len(samples) == 5
    assert samples[0]["consumption_l"] == 3.0
