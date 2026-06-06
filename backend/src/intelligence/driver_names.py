"""Fuzzy matching de nombres de pilotos (sin dependencias externas)."""

from __future__ import annotations

import difflib
import unicodedata
from functools import lru_cache


def normalize_name(name: str) -> str:
    """Quita acentos y pasa a minúsculas."""
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFD", name)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.lower().strip()


@lru_cache(maxsize=256)
def _normalized_known(known_tuple: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    return tuple((n, normalize_name(n)) for n in known_tuple)


def fuzzy_match(spoken: str, known: list[str], threshold: float = 0.8) -> tuple[str, float] | None:
    """Devuelve el mejor match (nombre, score) o None."""
    if not spoken or not known:
        return None
    spoken_norm = normalize_name(spoken)
    best_name = ""
    best_score = 0.0
    for original, norm in _normalized_known(tuple(known)):
        score = difflib.SequenceMatcher(None, spoken_norm, norm).ratio()
        if score > best_score:
            best_score = score
            best_name = original
    if best_score >= threshold:
        return best_name, best_score
    return None


def get_driver_by_partial(spoken: str, drivers: list[dict]) -> dict | None:
    """Busca piloto por apellido parcial o fuzzy sobre driver_name."""
    if not spoken or not drivers:
        return None
    spoken_norm = normalize_name(spoken)
    names = [d.get("driver_name", "") for d in drivers if d.get("driver_name")]
    match = fuzzy_match(spoken, names)
    if match:
        target, _ = match
        for d in drivers:
            if d.get("driver_name") == target:
                return d
    for d in drivers:
        name = normalize_name(d.get("driver_name", ""))
        parts = name.split()
        if any(spoken_norm in part or part.startswith(spoken_norm) for part in parts if len(spoken_norm) >= 3):
            return d
    return None
