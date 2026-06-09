from __future__ import annotations

TYRE_HOT_C = 105.0
TYRE_COOKING_C = 120.0
TYRE_WEAR_WARN_PCT = 75.0
BRAKE_WEAR_WARN_PCT = 80.0
ENGINE_TEMP_WARN_C = 105.0
BATTERY_LOW_SOC = 20.0

_WHEELS = ("fl", "fr", "rl", "rr")


def _wear_dict(telemetry: dict, strategy: dict, key: str) -> dict:
    block = strategy.get(key) or {}
    if isinstance(block, dict) and block:
        return block
    out: dict[str, float] = {}
    for w in _WHEELS:
        v = telemetry.get(f"{key}_{w}")
        if v is not None:
            out[w] = float(v)
    return out


def avg_tyre_wear(telemetry: dict, strategy: dict) -> float:
    wear = _wear_dict(telemetry, strategy, "tyre_wear")
    if wear:
        vals = [float(wear.get(w, 0) or 0) for w in _WHEELS]
    else:
        vals = [float(telemetry.get(f"tyre_wear_{w}", 0) or 0) for w in _WHEELS]
    return sum(vals) / 4.0 if vals else 0.0


def max_brake_wear(telemetry: dict, strategy: dict) -> float:
    wear = _wear_dict(telemetry, strategy, "brake_wear")
    if wear:
        vals = [float(wear.get(w, 0) or 0) for w in _WHEELS]
    else:
        vals = [float(telemetry.get(f"brake_wear_{w}", 0) or 0) for w in _WHEELS]
    return max(vals) if vals else 0.0


def tyre_temp_level(telemetry: dict) -> tuple[str, str] | None:
    hottest_w: str | None = None
    hottest_t = 0.0
    for w in _WHEELS:
        t = telemetry.get(f"tyre_temp_{w}")
        if t is None:
            continue
        tf = float(t)
        if tf > hottest_t:
            hottest_t = tf
            hottest_w = w
    if hottest_w is None:
        return None
    if hottest_t >= TYRE_COOKING_C:
        return hottest_w, "cooking"
    if hottest_t >= TYRE_HOT_C:
        return hottest_w, "hot"
    return None


def engine_overheat(telemetry: dict) -> tuple[str, float] | None:
    for key in ("engine_water_temp", "oil_temp", "engine_oil_temp"):
        raw = telemetry.get(key)
        if raw is not None and float(raw) > ENGINE_TEMP_WARN_C:
            return key, float(raw)
    return None


def battery_low(telemetry: dict) -> bool:
    charge = float(telemetry.get("battery_charge", 100.0))
    drain = float(telemetry.get("battery_drain", 0.0))
    regen = float(telemetry.get("battery_regen", 0.0))
    return charge < BATTERY_LOW_SOC and (regen - drain) < 0.0
