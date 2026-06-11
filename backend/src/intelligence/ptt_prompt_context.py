"""Contexto PTT filtrado por intención — evita volcar telemetría en saludos."""

from __future__ import annotations

import re
from typing import Any

from src.intelligence.time_format import format_laptime


def classify_ptt_question(question: str) -> str:
    """Clasifica pregunta PTT para decidir cuánto contexto enviar al LLM."""
    q = question.lower().strip()
    if re.search(
        r"\b(hola|buenas|buenos d[ií]as|buenas tardes|qu[eé] tal|c[oó]mo est[aá]s|"
        r"afirmativo|recibido|gracias|ok|vale)\b",
        q,
    ):
        return "casual"
    if re.search(r"\b(ritmo|vuelta r[aá]pida|mejor vuelta|pole|l[ií]der|primero|referencia)\b", q):
        return "pace"
    if re.search(r"\b(combustible|fuel|gasolina|vueltas restantes|boxes|box)\b", q):
        return "fuel"
    if re.search(r"\b(neum[aá]tico|goma|tyre|desgaste|temperatura)\b", q):
        return "tires"
    if re.search(r"\b(gap|distancia|delante|detr[aá]s|rival)\b", q):
        return "gap"
    if re.search(r"\b(da[nñ]o|toque|aver[ií]a|reparar)\b", q):
        return "damage"
    if re.search(r"\b(sesi[oó]n|pr[aá]ctica|quali|carrera|clima|lluvia|bandera|fcy|sc)\b", q):
        return "session"
    return "open"


def _comp_name(comp: dict[str, Any]) -> str:
    return str(comp.get("driver_name") or comp.get("name") or "").strip()


def _leader_best_lap(competitors: list[dict[str, Any]]) -> float:
    leaders = [c for c in competitors if int(c.get("standing_position") or 0) == 1]
    if leaders:
        return float(leaders[0].get("lap_time_best") or leaders[0].get("best_lap") or 0)
    best = 0.0
    for comp in competitors:
        lap = float(comp.get("lap_time_best") or comp.get("best_lap") or 0)
        if lap > 0.1 and (best <= 0.1 or lap < best):
            best = lap
    return best


def _session_brief(data: dict[str, Any]) -> str:
    clase = data.get("session_class") or data.get("player_class") or "?"
    tipo = data.get("session_type") or "?"
    temp = data.get("ambient_temp", "?")
    grip = data.get("grip", 0)
    grip_label = {0: "verde", 1: "baja", 2: "media", 3: "alta", 4: "saturada"}.get(int(grip or 0), "seca")
    return f"Sesión {tipo} {clase}, pista {grip_label}, {temp}°C ambiente."


def _pace_brief(data: dict[str, Any]) -> str:
    parts: list[str] = [_session_brief(data)]
    player_best = float(data.get("player_best_lap") or 0)
    leader_best = float(data.get("leader_best_lap") or 0)
    pos = data.get("position") or data.get("standing_position")
    if pos:
        parts.append(f"Tu posición: P{pos}.")
    if player_best > 0.1:
        parts.append(f"Tu mejor vuelta: {format_laptime(player_best, colloquial=True)}.")
    if leader_best > 0.1:
        parts.append(f"Referencia del líder: {format_laptime(leader_best, colloquial=True)}.")
    ahead = data.get("ahead_gap")
    behind = data.get("behind_gap")
    if ahead not in (None, 0, 0.0):
        parts.append(f"Gap adelante: +{float(ahead):.1f}s.")
    if behind not in (None, 0, 0.0):
        parts.append(f"Gap detrás: {float(behind):.1f}s.")
    return " ".join(parts)


def _compact_brief(data: dict[str, Any]) -> str:
    lap = data.get("lap") or data.get("lap_number") or 0
    pos = data.get("position") or data.get("standing_position") or "?"
    fuel = data.get("fuel")
    laps_rest = data.get("laps_rest")
    parts = [f"Vuelta {lap}, P{pos}."]
    if fuel is not None:
        parts.append(f"Combustible {fuel}L.")
    if laps_rest:
        parts.append(f"~{laps_rest} vueltas estimadas.")
    parts.append(_session_brief(data))
    return " ".join(parts)


def build_ptt_context_for_question(question: str, ticker_data: dict[str, Any], full_ticker: str) -> str:
    """Devuelve contexto acotado según la pregunta (no siempre el ticker completo)."""
    kind = classify_ptt_question(question)
    if kind == "casual":
        return _session_brief(ticker_data)
    if kind == "pace":
        return _pace_brief(ticker_data)
    if kind == "fuel":
        return _compact_brief(ticker_data)
    if kind == "tires":
        temps = ticker_data.get("tyre_temps") or []
        wear = ticker_data.get("tyre_wear") or []
        if len(temps) >= 4 and len(wear) >= 4:
            return (
                f"{_compact_brief(ticker_data)} "
                f"Desgaste FL/FR/RL/RR: {int(wear[0])}/{int(wear[1])}/{int(wear[2])}/{int(wear[3])}%. "
                f"Temp FL/FR/RL/RR: {int(temps[0])}/{int(temps[1])}/{int(temps[2])}/{int(temps[3])}°C."
            )
    if kind == "gap":
        return _pace_brief(ticker_data)
    if kind == "damage":
        return _compact_brief(ticker_data)
    if kind == "session":
        return _session_brief(ticker_data)
    # Pregunta abierta: resumen compacto, no ticker RIV completo
    return _compact_brief(ticker_data)
