"""Mensajes de daño estilo Crew Chief a partir de telemetría LMU."""

from __future__ import annotations

import math

from src.intelligence.crewchief_events.templates import render_template

IMPACT_MAGNITUDE_MIN = 25.0
IMPACT_SETTLE_S = 3.0
IMPACT_CRASH_THRESHOLD_MS2 = 392.0  # ~40G
# LMU a menudo deja mLastImpact* en 0; el spotter usa aceleración local como respaldo.
SPOTTER_ACCEL_IMPACT_MS2 = 120.0  # ~12G — impacto audible en pista
SPOTTER_ACCEL_COOLDOWN_S = 3.0
CRASH_POST_IMPACT_WAIT_S = 2.0
CRASH_LOW_SPEED_MS = 3.0
PUNCTURE_DELAY_S = 5.0

PUNCTURE_WHEEL_NAMES = [
    "delantero izquierdo",
    "delantero derecho",
    "trasero izquierdo",
    "trasero derecho",
]

_TYRE_FLAT_KEYS = ("tyre_flat_fl", "tyre_flat_fr", "tyre_flat_rl", "tyre_flat_rr")


def classify_damage_severity(tick: dict) -> str:
    """Devuelve leve | moderado | grave."""
    if bool(tick.get("detached", False)):
        return "grave"
    dent_max = int(tick.get("dent_severity_max", 0) or 0)
    dent_avg = float(tick.get("dent_severity_avg", 0) or 0)
    aero = float(tick.get("damage_aero", 0) or 0)
    if dent_max >= 2 or dent_avg >= 1.2 or aero >= 60.0:
        return "grave"
    if dent_max >= 1 or dent_avg >= 0.5 or aero >= 25.0:
        return "moderado"
    return "leve"


_WHEEL_KEYS = ("fl", "fr", "rl", "rr")


def _puncture_wheel_key(tick: dict) -> str | None:
    for i, key in enumerate(_TYRE_FLAT_KEYS):
        if tick.get(key, False):
            return _WHEEL_KEYS[i]
    return None


def format_impact_damage_message(tick: dict) -> str:
    """Mensaje tras un impacto nuevo (ingeniero / spotter)."""
    if bool(tick.get("detached", False)):
        return render_template("damage_impact", {"detached": True})
    severity = classify_damage_severity(tick)
    return render_template("damage_impact", {"severity": severity})


def local_accel_magnitude(tick: dict) -> float:
    ax = float(tick.get("local_accel_x", 0) or 0)
    ay = float(tick.get("local_accel_y", 0) or 0)
    az = float(tick.get("local_accel_z", 0) or 0)
    return math.sqrt(ax * ax + ay * ay + az * az)


def detect_puncture(tick: dict) -> tuple[bool, int]:
    """Detecta pinchazo vía mFlat. Retorna (hay_pinchazo, índice_rueda 0-3)."""
    for i, key in enumerate(_TYRE_FLAT_KEYS):
        if tick.get(key, False):
            return True, i
    return False, -1


def player_speed_ms(tick: dict) -> float:
    return math.hypot(float(tick.get("vel_x", 0) or 0), float(tick.get("vel_z", 0) or 0))


def detect_crash_g(tick: dict) -> bool:
    return local_accel_magnitude(tick) >= IMPACT_CRASH_THRESHOLD_MS2


def aero_damage_level(tick: dict) -> int:
    """0=ninguno, 1=leve, 2=moderado, 3=grave (solo aero)."""
    aero = float(tick.get("damage_aero", 0) or 0)
    if aero >= 60.0:
        return 3
    if aero >= 25.0:
        return 2
    if aero > 0.0:
        return 1
    return 0


def format_aero_damage_message(level: int) -> str:
    if level == 3:
        return render_template("damage_impact", {"severity": "grave"})
    if level == 2:
        return render_template("damage_impact", {"severity": "moderado"})
    if level == 1:
        return render_template("damage_impact", {"severity": "leve"})
    return ""


def format_puncture_message(wheel_index: int) -> str:
    wheel = _WHEEL_KEYS[wheel_index]
    return render_template("damage_puncture", {"wheel": wheel})


def count_flat_tyres(tick: dict) -> int:
    return sum(1 for key in _TYRE_FLAT_KEYS if tick.get(key))


def active_damage_items(tick: dict, *, include_impact: bool = False, impact_magnitude: float = 0.0) -> list[str]:
    """Categorías de daño activas (sin desglose por rueda)."""
    items: list[str] = []
    flat_count = count_flat_tyres(tick)
    if flat_count >= 2:
        items.append("multiple_punctures")
    elif flat_count == 1:
        items.append("puncture")

    level = aero_damage_level(tick)
    if level >= 3:
        items.append("aero_grave")
    elif level >= 2:
        items.append("aero_moderate")
    elif level >= 1:
        items.append("aero_leve")

    if bool(tick.get("detached", False)):
        items.append("detached")
    elif int(tick.get("dent_severity_max", 0) or 0) >= 2:
        items.append("dent_grave")
    elif int(tick.get("dent_severity_max", 0) or 0) >= 1:
        items.append("dent")

    if float(tick.get("suspension_damage", 0) or 0) >= 0.5:
        items.append("suspension")

    if include_impact:
        if impact_magnitude >= 80.0:
            items.append("impact_grave")
        elif impact_magnitude >= 50.0:
            items.append("impact_notable")
        elif impact_magnitude >= IMPACT_MAGNITUDE_MIN:
            items.append("impact_leve")

    return items


def damage_items_are_severe(items: list[str], tick: dict) -> bool:
    if any(
        item in items
        for item in ("detached", "multiple_punctures", "aero_grave", "dent_grave", "impact_grave")
    ):
        return True
    return classify_damage_severity(tick) == "grave"


def format_damage_status_message(
    tick: dict,
    items: list[str],
    *,
    impact_magnitude: float = 0.0,
) -> str | None:
    """Un solo mensaje según el conjunto de daños activos."""
    if not items:
        return None

    if len(items) >= 2:
        if damage_items_are_severe(items, tick):
            return "Múltiples daños en el coche. ¿Estás bien?"
        return render_template("damage_impact", {"severity": "moderado"})

    item = items[0]
    if item in ("puncture", "multiple_punctures"):
        if item == "multiple_punctures" or damage_items_are_severe(items, tick):
            return render_template("damage_puncture", {"multiple": True})
        wheel = _puncture_wheel_key(tick)
        if wheel:
            return render_template("damage_puncture", {"wheel": wheel})
        return render_template("damage_puncture")
    if item == "detached":
        return render_template("damage_impact", {"detached": True})
    if item.startswith("aero_"):
        return format_aero_damage_message(aero_damage_level(tick))
    if item == "impact_grave":
        return render_template("damage_impact", {"severity": "grave"})
    if item == "impact_notable":
        return render_template("damage_impact", {"severity": "moderado"})
    if item == "impact_leve":
        return render_template("damage_impact", {"severity": "leve"})
    if item in ("dent_grave", "suspension"):
        return render_template("damage_are_you_ok", {"attempt": 0})
    if item == "dent":
        return render_template("damage_impact", {"severity": "moderado"})
    if item == "aero_moderate":
        return format_aero_damage_message(2)
    return render_template("damage_impact", {"severity": "leve"})


CRASH_RETRY_MESSAGES = (
    "¿Estás bien? ¿Estás bien?",
    "¿Cómo estás? Responde.",
    "No contestas. Entra en boxes si puedes.",
)


def format_damage_summary(tick: dict) -> str:
    """Resumen de daño acumulado (commentary)."""
    severity = classify_damage_severity(tick)
    aero = float(tick.get("damage_aero", 0) or 0)
    if severity == "grave":
        return f"Daño grave — aero al {aero:.0f}%, considera reparar."
    if severity == "moderado":
        return f"Daño moderado — aero al {aero:.0f}%."
    return f"Daños leves — aero al {aero:.0f}%."
