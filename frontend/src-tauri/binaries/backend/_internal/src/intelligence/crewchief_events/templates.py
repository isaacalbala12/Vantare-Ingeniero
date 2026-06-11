"""Catálogo determinista de plantillas TTS estilo Crew Chief (español)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_TEMPLATES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "crewchief_templates_es.json"
)

# IDs legacy → clave de catálogo (+ variables implícitas)
_EVENT_ALIASES: dict[str, tuple[str, dict[str, Any]]] = {
    "penalty_2_laps": ("penalty_countdown", {"laps": 2}),
    "penalty_1_lap": ("penalty_countdown", {"laps": 1}),
    "overtake_position_gain": ("position_overtake", {}),
    "position_loss": ("position_lost", {}),
    "rain_light": ("rain_increasing", {"level": "light"}),
    "damage_crash_ok_0": ("damage_are_you_ok", {"attempt": 0}),
    "damage_crash_ok_1": ("damage_are_you_ok", {"attempt": 1}),
    "damage_crash_ok_2": ("damage_are_you_ok", {"attempt": 2}),
    "flags_fcy_pits_closed": ("fcy_pits_closed", {}),
    "flags_fcy_pits_open": ("fcy_pits_open", {}),
    "flags_fcy_last_lap": ("fcy_last_lap", {}),
    "flags_fcy_resume": ("fcy_prepare_green", {}),
    "flags_green": ("fcy_green", {}),
    "flags_fcy": ("fcy_pits_closed", {"safety_car": False}),
    "flags_safety_car": ("fcy_pits_closed", {}),
}

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, dict[str, Any]]:
    with open(_TEMPLATES_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def _coerce(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _variant_key(variables: dict[str, Any]) -> str | None:
    """Elige la variante más específica según variables (orden estable)."""
    if not variables:
        return None
    parts: list[str] = []
    for key in sorted(variables):
        parts.append(f"{key}={_coerce(variables[key])}")
    return parts[-1] if len(parts) == 1 else None


def _pick_variant(entry: dict[str, Any], variables: dict[str, Any]) -> str:
    variants: dict[str, str] = entry.get("variants") or {}
    if not variants:
        return str(entry.get("default") or "")

    # Coincidencia exacta compuesta (p. ej. severity=grave)
    composite = _variant_key(variables)
    if composite and composite in variants:
        return variants[composite]

    # Coincidencias parciales por clave individual
    for key in sorted(variables):
        candidate = f"{key}={_coerce(variables[key])}"
        if candidate in variants:
            return variants[candidate]

    return str(entry.get("default") or variants.get("default") or "")


def _apply_personality(template: str, entry: dict[str, Any], personality: str) -> str:
    personalities: dict[str, str] = entry.get("personalities") or {}
    pid = (personality or "standard").strip().lower()
    return personalities.get(pid, template)


def _format_template(template: str, variables: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            return match.group(0)
        return _coerce(variables[key])

    return _PLACEHOLDER_RE.sub(repl, template).strip()


def render_template(
    event_id: str,
    variables: dict[str, Any] | None = None,
    *,
    personality: str = "standard",
) -> str:
    """Resuelve texto TTS para un event_id CC con interpolación opcional."""
    merged: dict[str, Any] = dict(variables or {})
    catalog_key = event_id
    if event_id in _EVENT_ALIASES:
        catalog_key, alias_vars = _EVENT_ALIASES[event_id]
        for key, value in alias_vars.items():
            merged.setdefault(key, value)

    catalog = _load_catalog()
    entry = catalog.get(catalog_key)
    if entry is None:
        return ""

    raw = _pick_variant(entry, merged)
    raw = _apply_personality(raw, entry, personality)
    return _format_template(raw, merged)


def list_template_ids() -> list[str]:
    return sorted(_load_catalog().keys())
