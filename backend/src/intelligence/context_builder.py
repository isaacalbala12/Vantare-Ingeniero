"""Construcción de prompts para el LLM con soporte RAG.

Toma el snapshot del tier adecuado, añade metadatos del trigger y la pregunta
del piloto si existe, y renderiza el prompt completo.

Si hay un EventStore configurado, inyecta los top-5 eventos históricos más
similares a la telemetría actual como contexto RAG.
"""

from typing import Any, Optional


def build_prompt(
    snapshot: dict,
    trigger_reason: str,
    pilot_question: Optional[str],
    templates: Any,
    event_store: Optional[Any] = None,
) -> str:
    """Construye el prompt completo para el LLM.

    Args:
        snapshot: Diccionario con snapshot de telemetría actual.
        trigger_reason: Razón del trigger que activó la llamada.
        pilot_question: Pregunta directa del piloto (opcional).
        templates: Módulo prompt_templates con render().
        event_store: EventStore opcional para RAG.

    Returns:
        String del prompt completo renderizado.
    """
    context_dict: dict = {
        "snapshot": snapshot,
        "trigger_reason": trigger_reason,
    }
    if pilot_question:
        context_dict["pilot_question"] = pilot_question

    # Inyectar RAG: top-5 eventos históricos con telemetría similar
    rag_context = _build_rag_context(snapshot, event_store)
    if rag_context:
        context_dict["rag_context"] = rag_context

    # Determinar tier para template
    tier = "FAST"
    if "tyre_compound" in snapshot:
        tier = "STANDARD"
    if "weather_forecast" in snapshot:
        tier = "DEEP"

    return templates.render(context_dict, tier)


def build_prompt_for_question(
    snapshot: dict,
    pilot_question: str,
    chat_history: Optional[list] = None,
    templates: Optional[Any] = None,
    event_store: Optional[Any] = None,
) -> str:
    """Construye prompt para pregunta directa del piloto con RAG."""
    context_dict: dict = {
        "snapshot": snapshot,
        "pilot_question": pilot_question,
    }
    if chat_history:
        context_dict["chat_history"] = chat_history

    # RAG
    rag_context = _build_rag_context(snapshot, event_store)
    if rag_context:
        context_dict["rag_context"] = rag_context

    tier = "FAST"
    if snapshot.get("lap_number", 0) > 0 and (snapshot.get("speed") or snapshot.get("fuel")):
        tier = "STANDARD"
    if snapshot.get("weather_forecast"):
        tier = "DEEP"

    if templates is None:
        from src.intelligence import prompt_templates as templates
    return templates.render(context_dict, tier)


def _build_rag_context(
    snapshot: dict,
    event_store: Optional[Any] = None,
    top_k: int = 5,
) -> Optional[str]:
    """Consulta el EventStore y devuelve un string formateado con los top-k eventos.

    Si no hay EventStore o la consulta no devuelve resultados, retorna None.
    """
    if event_store is None:
        return None

    # Convertir snapshot a formato frame para la query
    frame = _snapshot_to_frame(snapshot)
    if not frame:
        return None

    results = event_store.query(frame, top_k=top_k)
    if not results:
        return None

    lines: list[str] = ["## RECORDATORIO HISTÓRICO"]
    for r in results:
        lap = r.get("lap", 0)
        etype = r.get("type", "unknown")
        text = r.get("text", "")
        summary = _summarize_event(text, etype, lap)
        lines.append(f"- V{lap}: {summary}")

    return "\n".join(lines)


def _snapshot_to_frame(snapshot: dict) -> Optional[dict]:
    """Convierte un snapshot de LiveContextManager a formato frame para EventStore query."""
    if not snapshot:
        return None

    fuel_val = snapshot.get("fuel_in_tank", 0.0)
    if isinstance(fuel_val, str):
        try:
            fuel_val = float(fuel_val)
        except (TypeError, ValueError):
            fuel_val = 0.0

    return {
        "lap_number": snapshot.get("lap", 0),
        "standing_position": snapshot.get("position", snapshot.get("place", 0)),
        "fuel_in_tank": fuel_val,
        "tyre_wear_fl": snapshot.get("tyre_wear_fl", snapshot.get("wear_fl", 0.0)),
        "tyre_wear_fr": snapshot.get("tyre_wear_fr", snapshot.get("wear_fr", 0.0)),
        "tyre_wear_rl": snapshot.get("tyre_wear_rl", snapshot.get("wear_rl", 0.0)),
        "tyre_wear_rr": snapshot.get("tyre_wear_rr", snapshot.get("wear_rr", 0.0)),
        "safety_car_active": snapshot.get("safety_car_active", False),
        "yellow_flag_active": snapshot.get("yellow_flag_active", False),
        "full_course_yellow_active": snapshot.get("full_course_yellow_active", False),
        "time_gap_place_ahead": snapshot.get("gap_ahead", 0.0),
        "time_gap_place_behind": snapshot.get("gap_behind", 0.0),
        "speed": snapshot.get("speed", 0.0),
        "battery_charge": snapshot.get("battery_charge", 100.0),
        "session_type": snapshot.get("phase", "race"),
        "cloud_coverage": snapshot.get("cloud_coverage", 0),
        "raining": snapshot.get("raining", 0.0),
        "avg_path_wetness": snapshot.get("avg_path_wetness", 0.0),
        "ambient_temp": snapshot.get("ambient_temp", 20.0),
        "track_temp": snapshot.get("track_temp", 20.0),
        "drs_state": snapshot.get("drs_state", False),
        "rear_flap_activated": snapshot.get("rear_flap_activated", False),
        "pit_state": snapshot.get("pit_state", 0),
    }


def _summarize_event(text: str, event_type: str, lap: int) -> str:
    """Genera un resumen legible del evento a partir del texto embedido."""
    parts = text.split("|")
    info: dict[str, str] = {}
    for p in parts:
        if p.startswith("P"):
            info["pos"] = p[1:]
        elif p.startswith("F"):
            info["fuel"] = p[1:]
        elif p.startswith("T"):
            info["tyres"] = p[1:]
        elif p == "SCS":
            info["sc"] = "SC activo"
        elif p.startswith("G"):
            info["gap"] = p[1:]

    summary_parts: list[str] = []
    type_descriptions = {
        "lap_completed": "Vuelta completada",
        "pit_entry": "Entrada a boxes",
        "pit_exit": "Salida de boxes",
        "safety_car": "Safety Car desplegado",
        "yellow_flag": "Bandera amarilla",
        "position_change": "Cambio de posición",
        "gap_change": "Cambio de gap",
        "weather_change": "Cambio climático",
    }
    summary_parts.append(type_descriptions.get(event_type, event_type))

    if info.get("sc") == "SC activo":
        summary_parts.append("(SC)")
    if "pos" in info:
        summary_parts.append(f"P{info['pos']}")
    if "fuel" in info:
        summary_parts.append(f"Comb.{info['fuel']}L")
    if "tyres" in info:
        avg_wear = _avg_tyre_wear(info["tyres"])
        summary_parts.append(f"Neum.{avg_wear:.0f}%")

    return " | ".join(summary_parts)


def _avg_tyre_wear(tyre_str: str) -> float:
    """Calcula el desgaste promedio de neumáticos desde string tipo '72/68/65/63'."""
    try:
        vals = [float(v) for v in tyre_str.split("/")]
        return sum(vals) / len(vals) if vals else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0
