from __future__ import annotations


from src.intelligence.state_coercion import lmu_scalar


def build_lmu_session_context(raw: dict) -> dict:
    damage_multi = lmu_scalar(raw.get("SESSSET_Damage_Multi"), 1.0)
    fuel_usage = lmu_scalar(raw.get("SESSSET_Fuel_Usage"), 1.0)
    return {
        "damage_enabled": damage_multi > 0,
        "fuel_multiplier": fuel_usage if fuel_usage > 0 else 1.0,
    }
