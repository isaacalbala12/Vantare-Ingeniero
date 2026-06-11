"""Convierte objetos de telemetría/estrategia a dict plano para el engine."""

from __future__ import annotations

from typing import Any


def lmu_scalar(node: object, default: float = 0.0) -> float:
    """LMU REST devuelve algunos campos como { currentValue, stringValue }."""
    if isinstance(node, dict):
        node = node.get("currentValue", default)
    try:
        return float(node)
    except (TypeError, ValueError):
        return default


def coerce_state_dict(obj: Any, *, allow_mock: bool = False) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        dump = obj.model_dump
        try:
            result = dump(mode="json")
        except TypeError:
            result = dump()
        if isinstance(result, dict):
            return result
    if allow_mock:
        from unittest.mock import Mock

        if isinstance(obj, Mock):
            result: dict[str, Any] = {}
            for key in dir(obj):
                if key.startswith("_") or key.startswith("assert_") or key.startswith("mock_"):
                    continue
                try:
                    value = getattr(obj, key)
                except AttributeError:
                    continue
                if isinstance(value, Mock) or callable(value):
                    continue
                result[key] = value
            return result
    if hasattr(obj, "dict"):
        return obj.dict()
    try:
        return vars(obj)
    except TypeError:
        return {}
