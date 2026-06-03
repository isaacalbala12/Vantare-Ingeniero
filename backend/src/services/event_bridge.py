"""Bridge adaptador: Convierte QueuedMessage del EventEngine a CrewChiefAlertMessage.

Ruta dedicada (no acoplada a AudioPlayer).
Llamado desde main.py como broadcast_callback del AudioPlayer.
"""
import logging
from typing import Dict, Any, Optional

from src.models.messages import CrewChiefAlertMessage, QueuedMessage

logger = logging.getLogger("vantare.event_bridge")

# Mapping table: message name prefixes -> category
_CATEGORY_MAP: Dict[str, str] = {
    # Fuel events
    "fuel": "fuel",
    # Tyre events
    "tyre": "tyres",
    "tyres": "tyres",
    # Position events
    "position": "position",
    "overtake": "position",
    "leading": "position",
    "start": "position",
    # Pit stop events
    "pit": "pit_stops",
    # Pit limiter events (separate from pit_stops)
    "limiter": "pit_limiter",
    # Battery events
    "battery": "battery",
    "ve_": "battery",
    "virtual_energy": "battery",
    # Damage events
    "damage": "damage",
    "aero": "damage",
    "suspension": "damage",
    # Engine events
    "engine": "engine",
    "water_temp": "engine",
    "oil": "engine",
    # Flag events
    "flag": "flags",
    "fcy": "flags",
    "yellow": "flags",
    "safety": "flags",
    "green": "flags",
    # Condition events
    "condition": "conditions",
    "weather": "conditions",
    "rain": "conditions",
    "track_temp": "conditions",
    "ambient": "conditions",
    # Frozen order
    "frozen": "frozen_order",
    "formation": "frozen_order",
    # Session events
    "session": "session",
    "last_lap": "session",
    "chequered": "session",
    # Spotter events
    "car_left": "spotter",
    "car_right": "spotter",
    "car_ahead": "spotter",
    "three_wide": "spotter",
    "clear_left": "spotter",
    "clear_right": "spotter",
    "holding": "spotter",
    "still_there": "spotter",
}


def _infer_category(msg: QueuedMessage) -> str:
    """Infers category from message name by prefix matching."""
    name = msg.name.lower() if msg.name else ""
    for prefix, category in _CATEGORY_MAP.items():
        if name.startswith(prefix):
            return category
    return "general"


def _map_severity(priority: int) -> str:
    """Maps AudioPlayer numeric priority to severity string.

    20 (spotter) -> critical
    15 (critical) -> critical
    10 (important) -> high
    8 (voice) -> medium
    5 (normal) -> low
    """
    if priority >= 15:
        return "critical"
    elif priority >= 10:
        return "high"
    elif priority >= 8:
        return "medium"
    return "low"


def _format_message(msg: QueuedMessage) -> str:
    """Formats a QueuedMessage into human-readable alert text for the frontend.

    Normalizes the message name by:
        - Replacing underscores with spaces and applying title case
        - Stripping technical suffixes like ' Monitor', ' Event', ' Reporting'

    Args:
        msg: QueuedMessage from the EventEngine (fuel_low, car_left, etc.).

    Returns:
        Human-readable alert string. Defaults to 'CrewChief Alert' if name is empty.
    """
    if not msg.name:
        return "CrewChief Alert"

    readable = msg.name.replace("_", " ").title()

    # Normalize technical suffixes so labels stay human-readable.
    for suffix in (" Monitor", " Event", " Reporting"):
        if readable.endswith(suffix):
            readable = readable[: -len(suffix)]

    return readable


def queued_to_crewchief_alert(qmsg: QueuedMessage) -> CrewChiefAlertMessage:
    """Converts QueuedMessage from EventEngine to CrewChiefAlertMessage for frontend.

    Args:
        qmsg: Mensaje de cola del EventEngine (fuel_low, car_left, etc.)

    Returns:
        CrewChiefAlertMessage listo para enviar por WebSocket
    """
    category = _infer_category(qmsg)
    subtype = qmsg.name or "unknown"
    message = _format_message(qmsg)
    severity = _map_severity(qmsg.priority)

    return CrewChiefAlertMessage(
        category=category,
        subtype=subtype,
        message=message,
        severity=severity,
        audio_priority=qmsg.priority,
        payload=qmsg.validation or {},
    )
