from __future__ import annotations

import re
from dataclasses import dataclass
from unicodedata import combining, normalize

@dataclass(frozen=True)
class FastCommand:
    intent: str
    phrase: str


def _clean(text: str) -> str:
    decomposed = normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not combining(ch)).strip()


def match_fast_command(text: str) -> FastCommand | None:
    cleaned = _clean(text)
    spotter = match_spotter_fast_command(text)
    if spotter == "enable":
        return FastCommand(intent="spotter_enable", phrase=text)
    if spotter == "disable":
        return FastCommand(intent="spotter_disable", phrase=text)
    patterns = {
        "fuel_status": ("combustible", "gasolina", "fuel"),
        "damage_status": ("danos", "dano", "damage"),
        "gap_status": ("gap", "distancia", "delante", "detras"),
        "speak_only_on": (
            "callate",
            "cállate",
            "calmate",
            "cálmate",
            "silencio",
            "solo cuando te pregunte",
            "no digas nada",
            "no hables",
            "para de hablar",
            "basta de hablar",
            "shhh",
            "shh",
            "calla",
        ),
        "speak_only_off": ("puedes hablar", "habla normal", "quita silencio", "vuelve a hablar"),
    }
    for intent, needles in patterns.items():
        if any(needle in cleaned for needle in needles):
            return FastCommand(intent=intent, phrase=text)
    return None


def match_spotter_fast_command(text: str) -> str | None:
    """Circuit breaker spotter — mirrors frontend spotterCommands.ts."""
    normalized = _clean(text)
    if not normalized:
        return None
    enable = (
        r"^spot$",
        r"^espiar$",
        r"^activa(r)? el spotter$",
        r"^modo spotter$",
    )
    disable = (
        r"^don'?t spot$",
        r"^deja de espiar$",
        r"^para(r)? el spotter$",
        r"^silencio spotter$",
        r"^spotter off$",
    )
    if any(re.search(p, normalized) for p in enable):
        return "enable"
    if any(re.search(p, normalized) for p in disable):
        return "disable"
    return None
