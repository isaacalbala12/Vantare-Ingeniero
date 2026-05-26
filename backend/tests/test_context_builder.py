from src.intelligence.context_builder import build_prompt, _build_ticker_data
from src.intelligence import prompt_templates


def test_build_ticker_data_has_fields():
    snapshot = {"lap": 5, "fuel_in_tank": 42.0, "place": 3, "gap_ahead": 2.1, "gap_behind": 1.5, "phase": "RACE"}
    data = _build_ticker_data(snapshot)
    assert "position" in data
    assert "lap" in data
    assert "fuel" in data
    assert "tyre_wear" in data  # lista [fl, fr, rl, rr]
    assert "brake_wear" in data  # lista [fl, fr, rl, rr]


def test_build_prompt_with_ticker():
    snapshot = {"lap": 5, "fuel_in_tank": 42.0, "place": 3}
    telemetry = {"competitors": [], "session_type": "race", "session_time_left": 3600}
    result = build_prompt(snapshot, "test", None, prompt_templates, telemetry_frame=telemetry)
    assert "DRV:P" in result


def test_build_prompt_legacy():
    snapshot = {"lap": 5, "fuel_in_tank": 42.0, "place": 3}
    result = build_prompt(snapshot, "test", None, prompt_templates)
    # Modo legacy: usa SYSTEM_PROMPT_BASIC + no contiene ticker
    assert "Eres un ingeniero de carrera" in result
    assert "DRV:P" not in result
