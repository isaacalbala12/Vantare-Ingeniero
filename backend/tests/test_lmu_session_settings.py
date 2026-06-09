from src.intelligence.crewchief_events.lmu_context import build_lmu_session_context


def test_session_context_reads_damage_and_fuel_multiplier():
    raw = {
        "SESSSET_Damage_Multi": {"currentValue": 0},
        "SESSSET_Fuel_Usage": {"currentValue": 2},
    }

    ctx = build_lmu_session_context(raw)

    assert ctx["damage_enabled"] is False
    assert ctx["fuel_multiplier"] == 2.0


def test_session_context_defaults_safe_when_missing():
    ctx = build_lmu_session_context({})

    assert ctx["damage_enabled"] is True
    assert ctx["fuel_multiplier"] == 1.0


def test_get_session_settings_returns_cached_copy():
    from src.services import lmu_api

    with lmu_api._cache_lock:
        lmu_api._session_settings_cache = {"SESSSET_Fuel_Usage": {"currentValue": 1}}
        lmu_api._session_settings_updated = 1.0

    snap = lmu_api.get_session_settings()
    assert snap["SESSSET_Fuel_Usage"]["currentValue"] == 1
    snap["extra"] = True
    with lmu_api._cache_lock:
        assert "extra" not in lmu_api._session_settings_cache

    with lmu_api._cache_lock:
        lmu_api._session_settings_cache = {}
        lmu_api._session_settings_updated = 0.0
