"""
MessagePack + Delta encoding codec for telemetry frames.

Provides encode/decode for binary MessagePack transport and
delta computation/application for efficient 20Hz telemetry streaming.

Frame format:
  - Delta:   {_t: float, <changed fields...>}
  - Full:    {_t: float, _full: True, <all fields...>}
"""

from __future__ import annotations

import time
from typing import Any

import msgpack  # type: ignore[import-untyped]


def encode(data: dict[str, Any]) -> bytes:
    """Encode a Python dict to MessagePack binary bytes."""
    result: bytes = msgpack.packb(data)
    return result


def decode(raw: bytes) -> dict[str, Any]:
    """Decode MessagePack binary bytes to a Python dict."""
    result: dict[str, Any] = msgpack.unpackb(raw)
    return result


def apply_delta(base: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    """Merge a delta dict onto a base dict, returning a new dict.

    Fields present in delta overwrite corresponding fields in base.
    Fields NOT present in delta retain their base values.
    Internal fields (_t, _full) are excluded from the merge.
    The base dict is never mutated.
    """
    result = dict(base)  # shallow copy
    for key, value in delta.items():
        if key.startswith("_"):
            continue
        result[key] = value
    return result


def compute_delta(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    *,
    force_full: bool = False,
) -> dict[str, Any]:
    """Compute a delta from previous frame to current frame.

    Args:
        previous: The previous telemetry frame (None on first invocation).
        current: The current telemetry frame.
        force_full: If True, emit a full snapshot regardless of diff.

    Returns:
        A dict with _t (timestamp) and optionally _full=True.
        Only fields that changed vs previous are included.
        If previous is None, emits a full snapshot.
    """
    ts = time.time()
    if previous is None or force_full:
        result = dict(current)
        result["_full"] = True
        result["_t"] = ts
        return result

    delta: dict[str, Any] = {"_t": ts}
    for key, value in current.items():
        if key not in previous or previous[key] != value:
            delta[key] = value
    return delta


def is_full_frame(frame: dict[str, Any]) -> bool:
    """Return True if the frame is a full snapshot (_full=True)."""
    return bool(frame.get("_full", False))
