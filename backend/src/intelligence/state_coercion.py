"""Convierte objetos de telemetría/estrategia a dict plano para el engine."""

from __future__ import annotations

from typing import Any


def coerce_state_dict(obj: Any, *, allow_mock: bool = False) -> dict[str, Any]:
    if allow_mock:
        from unittest.mock import Mock

        if isinstance(obj, Mock):
            result: dict[str, Any] = {}
            for key in dir(obj):
                if key.startswith("_"):
                    continue
                try:
                    value = getattr(obj, key)
                except AttributeError:
                    continue
                if isinstance(value, Mock):
                    continue
                result[key] = value
            return result
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "dict"):
        return obj.dict()
    try:
        return vars(obj)
    except TypeError:
        return {}
