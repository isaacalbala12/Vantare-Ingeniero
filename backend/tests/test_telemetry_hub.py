from src.race.telemetry_hub import TelemetryHub


def test_hub_stores_latest_snapshot_and_advice():
    hub = TelemetryHub()
    hub.update(snapshot={"lap": 3, "speed_ms": 50.0}, advice={"fuel_laps": 2})
    snap, adv = hub.get_latest()
    assert snap["lap"] == 3
    assert adv["fuel_laps"] == 2


def test_hub_returns_copy_not_reference():
    hub = TelemetryHub()
    original = {"lap": 1}
    hub.update(snapshot=original, advice=None)
    original["lap"] = 99
    snap, _ = hub.get_latest()
    assert snap["lap"] == 1
