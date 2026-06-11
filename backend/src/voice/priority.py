from __future__ import annotations

import re
from typing import Literal

PlayPriority = Literal["IMMEDIATE", "NORMAL"]

IMMEDIATE_CATEGORIES = frozenset({"proximity", "limiter", "fuel", "safety_car"})

IMMEDIATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^coche a la (izquierda|derecha)$", re.I),
    re.compile(r"^despejado (izquierda|derecha)$", re.I),
    re.compile(r"^tres coches de ancho$", re.I),
    re.compile(r"mant[eé]n la l[ií]nea", re.I),
    re.compile(r"viene r[aá]pido por", re.I),
    re.compile(r"hypercar", re.I),
    re.compile(r"doblando por la (izquierda|derecha)$", re.I),
    re.compile(r"adelantando por la (izquierda|derecha)$", re.I),
    re.compile(r"^sigue coche por (izquierda|derecha)", re.I),
    re.compile(r"pit limiter", re.I),
    re.compile(r"combustible cr[ií]tico", re.I),
    re.compile(r"safety car", re.I),
    re.compile(r"fcy activo", re.I),
    re.compile(r"última vuelta", re.I),
]


def normalize_tts_text(text: str) -> str:
    t = " ".join(text.strip().split())
    return t.rstrip(".!?…")


def classify_tts_priority(text: str, payload: dict | None = None) -> PlayPriority:
    payload = payload or {}
    category = str(payload.get("category") or "").lower()
    severity = str(payload.get("severity") or "").upper()
    raw = payload.get("audio_priority")
    as_num = int(raw) if isinstance(raw, int) else int(str(raw or "nan") if str(raw or "").isdigit() else -1)

    if category in IMMEDIATE_CATEGORIES:
        return "IMMEDIATE"
    if severity in ("CRITICAL", "HIGH"):
        return "IMMEDIATE"
    if as_num >= 3:
        return "IMMEDIATE"

    normalized = normalize_tts_text(text)
    if any(p.search(normalized) for p in IMMEDIATE_PATTERNS):
        return "IMMEDIATE"
    return "NORMAL"


def map_alert_to_play_priority(
    *,
    text: str,
    audio_priority: str,
    payload: dict | None,
) -> Literal["IMMEDIATE", "NORMAL", "ENGINEER"]:
    payload = payload or {}
    qc = str(payload.get("queue_class") or "").upper()
    if qc == "IMMEDIATE":
        return "IMMEDIATE"
    if str(payload.get("category") or "").lower() == "voice_response":
        return "ENGINEER"
    if audio_priority.upper() in ("IMPORTANT", "IMMEDIATE", "CRITICAL", "HIGH"):
        return "IMMEDIATE"
    if classify_tts_priority(text, payload) == "IMMEDIATE":
        return "IMMEDIATE"
    return "NORMAL"
