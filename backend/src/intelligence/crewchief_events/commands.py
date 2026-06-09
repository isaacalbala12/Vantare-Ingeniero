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


def count_fast_intent_groups(text: str) -> int:
    """Cuenta grupos de intención distintos (0 = pregunta abierta, 2+ = mixta)."""
    cleaned = _clean(text)
    groups = 0
    if match_spotter_fast_command(text) is not None:
        groups += 1
    intent_needles = (
        ("combustible", "gasolina", "fuel"),
        ("danos", "dano", "damage"),
        ("gap", "distancia", "delante", "detras"),
        (
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
        ("puedes hablar", "habla normal", "quita silencio", "vuelve a hablar"),
    )
    for needles in intent_needles:
        if any(needle in cleaned for needle in needles):
            groups += 1
    return groups


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


def match_radio_check(text: str) -> bool:
    """Check de radio puro: confirmar recepción sin volcar telemetría."""
    cleaned = _clean(text)
    cleaned = re.sub(r"[?.!,¿¡]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return False

    other_topic_markers = (
        "combustible",
        "fuel",
        "gasolina",
        "ritmo",
        "estrategia",
        "neumatic",
        "vuelta",
        "gap",
        "dano",
        "damage",
        "boxes",
        "tiempo",
        "posicion",
        "como va",
        "como esta",
        "que tal",
        "carrera",
        "lluvia",
        "clima",
        "temperatura",
        "desgaste",
    )
    if any(marker in cleaned for marker in other_topic_markers):
        return False

    radio_markers = (
        "me escuchas",
        "me oyes",
        "me recibes",
        "me ois",
        "radio check",
        "prueba de radio",
        "estas ahi",
        "esta ahi",
        "me escuchas ingeniero",
        "ingeniero me escuchas",
        "me oyes ingeniero",
    )
    return any(marker in cleaned for marker in radio_markers)


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
