from src.intelligence.context_builder import build_prompt, _build_ticker_data
from src.intelligence import prompt_templates


def test_build_ticker_data_has_fields():
    snapshot = {"lap": 5, "fuel_in_tank": 42.0, "place": 3, "gap_ahead": 2.1, "gap_behind": 1.5, "phase": "RACE"}
    data = _build_ticker_data(snapshot)
    assert "position" in data
    assert "lap" in data
    assert "fuel_in_tank" in data
    assert "tyre_wear_fl" in data
    assert "brake_wear" in data


def test_build_prompt_with_ticker():
    snapshot = {"lap": 5, "fuel_in_tank": 42.0, "place": 3}
    telemetry = {"competitors": [], "session_type": "race", "session_time_left": 3600}
    result = build_prompt(snapshot, "test", None, prompt_templates, telemetry_frame=telemetry)
    assert "DRV:P" in result


def test_build_prompt_legacy():
    snapshot = {"lap": 5, "fuel_in_tank": 42.0, "place": 3}
    result = build_prompt(snapshot, "test", None, prompt_templates)
    assert "snapshot" in result
