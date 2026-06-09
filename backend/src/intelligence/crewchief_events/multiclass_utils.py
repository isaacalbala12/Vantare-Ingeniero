from __future__ import annotations

_CLASS_RANK = {
    "GT3": 1,
    "LMP3": 2,
    "LMP2": 3,
    "GTE": 3,
    "HYPERCAR": 5,
    "LMH": 5,
    "HY": 5,
}


def normalize_class(name: str) -> str:
    n = (name or "").upper().replace(" ", "")
    if n in ("HY", "HYPERCAR", "LMH"):
        return "HYPERCAR"
    return n


def class_rank(name: str) -> int:
    return _CLASS_RANK.get(normalize_class(name), 2)


def is_similar_class(a: str, b: str) -> bool:
    return normalize_class(a) == normalize_class(b)
