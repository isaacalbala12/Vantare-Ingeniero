from __future__ import annotations


def _scalar(node: object, default: float) -> float:
    if isinstance(node, dict):
        node = node.get("currentValue", default)
    try:
        return float(node)
    except (TypeError, ValueError):
        return default


def build_lmu_session_context(raw: dict) -> dict:
    damage_multi = _scalar(raw.get("SESSSET_Damage_Multi"), 1.0)
    fuel_usage = _scalar(raw.get("SESSSET_Fuel_Usage"), 1.0)
    return {
        "damage_enabled": damage_multi > 0,
        "fuel_multiplier": fuel_usage if fuel_usage > 0 else 1.0,
    }
