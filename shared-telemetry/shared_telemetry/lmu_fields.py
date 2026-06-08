"""Helpers para campos LMU shared memory (Wave 1 parity)."""

from __future__ import annotations


def parse_yellow_flag_state(raw) -> int:
    """Convierte mYellowFlagState (c_char) a int -1..7."""
    if raw is None:
        return 0
    if isinstance(raw, (bytes, bytearray)):
        return int(raw[0]) if raw else 0
    if isinstance(raw, str):
        return ord(raw[0]) if raw else 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def lmu_sector_number(m_sector: int) -> int:
    """LMU mSector: 0=sector3, 1=sector1, 2=sector2 → 1..3."""
    mapping = {0: 3, 1: 1, 2: 2}
    return mapping.get(int(m_sector) & 0x7F, 0)
