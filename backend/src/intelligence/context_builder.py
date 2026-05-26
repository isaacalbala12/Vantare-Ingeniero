"""Construcción de prompts para el LLM con soporte RAG.

Toma el snapshot del tier adecuado, añade metadatos del trigger y la pregunta
del piloto si existe, y renderiza el prompt completo.

Si hay un EventStore configurado, inyecta los top-5 eventos históricos más
similares a la telemetría actual como contexto RAG.
"""

from typing import Any, Optional


def _build_ticker_data(snapshot, telemetry_frame=None, strategy_advice=None, lmu_api=None):
    """Construye el diccionario de datos para generate_ticker desde snapshot y fuentes adicionales."""
    data = {}
    data["position"] = snapshot.get("position", snapshot.get("place", 0))
    data["lap"] = snapshot.get("lap", 0)
    data["fuel_in_tank"] = snapshot.get("fuel_in_tank", 0.0)

    fuel_laps = 0
    fuel_rate = 0
    if strategy_advice:
        fuel_info = strategy_advice.get("fuel", {})
        fuel_laps = fuel_info.get("estimated_laps_remaining", fuel_info.get("laps_left", 0))
        fuel_rate = fuel_info.get("fuel_rate_trend", 0)
    data["fuel_rate"] = fuel_rate
    data["fuel_laps_left"] = fuel_laps

    if telemetry_frame:
        for wheel in ["fl", "fr", "rl", "rr"]:
            data[f"tyre_wear_{wheel}"] = telemetry_frame.get(f"tyre_wear_{wheel}", 0.0)
            data[f"tyre_temp_{wheel}"] = telemetry_frame.get(f"tyre_temp_{wheel}", 90.0)
    else:
        for wheel in ["fl", "fr", "rl", "rr"]:
            data[f"tyre_wear_{wheel}"] = snapshot.get(f"tyre_wear_{wheel}", 0.0)
            data[f"tyre_temp_{wheel}"] = snapshot.get(f"tyre_temp_{wheel}", 90.0)

    brake_wear = [0, 0, 0, 0]
    if lmu_api is not None:
        try:
            brakes_data = lmu_api.get_additional_data("brakes")
            if isinstance(brakes_data, dict):
                bw = brakes_data.get("wear", [])
                if bw and len(bw) == 4:
                    brake_wear = [int(w * 100) for w in bw]
        except Exception:
            pass
    data["brake_wear"] = brake_wear

    data["ahead_name"] = snapshot.get("ahead_name", "")
    data["ahead_gap"] = snapshot.get("gap_ahead", 0)
    data["ahead_best"] = 0
    data["behind_name"] = snapshot.get("behind_name", "")
    data["behind_gap"] = snapshot.get("gap_behind", 0)
    data["behind_best"] = 0
    data["delta"] = 0

    competitors = []
    if telemetry_frame:
        competitors = telemetry_frame.get("competitors", [])
    data["competitors"] = competitors
    data["total_cars"] = len(competitors)

    data["session_class"] = telemetry_frame.get("session_class", "GT3") if telemetry_frame else "GT3"
    data["session_type"] = telemetry_frame.get("session_type", snapshot.get("phase", "RACE")) if telemetry_frame else snapshot.get("phase", "RACE")
    data["total_laps"] = telemetry_frame.get("session_laps_left", 0) if telemetry_frame else 0
    data["time_left"] = telemetry_frame.get("session_time_left", 0) if telemetry_frame else 0

    data["grip"] = snapshot.get("track_grip_level", 0)
    data["ambient_temp"] = snapshot.get("ambient_temp", 20)
    data["rain_chance"] = 0
    data["rain_min"] = 0
    data["safety_car_active"] = telemetry_frame.get("safety_car_active", False) if telemetry_frame else False
    data["cloud_coverage"] = snapshot.get("cloud_coverage", 0)
    data["raining"] = snapshot.get("raining", 0.0)
    data["avg_path_wetness"] = telemetry_frame.get("avg_path_wetness", 0.0) if telemetry_frame else 0.0
    data["track_temp"] = telemetry_frame.get("track_temp", 20) if telemetry_frame else 20

    data["speed"] = snapshot.get("speed", 0)
    data["drs_state"] = telemetry_frame.get("drs_state", False) if telemetry_frame else False
    data["pit_state"] = telemetry_frame.get("pit_state", 0) if telemetry_frame else 0
    data["battery_charge"] = snapshot.get("battery_charge", 100)

    data["player_best_lap"] = telemetry_frame.get("lap_time_best", 0) if telemetry_frame else 0

    return data


def build_prompt(
    snapshot: dict,
    trigger_reason: str,
    pilot_question: Optional[str],
    templates: Any,
    event_store: Optional[Any] = None,
    telemetry_frame: Optional[dict] = None,
    strategy_advice: Optional[dict] = None,
    lmu_api: Optional[Any] = None,
) -> str:
    """Construye el prompt completo para el LLM.

    Args:
        snapshot: Diccionario con snapshot de telemetría actual.
        trigger_reason: Razón del trigger que activó la llamada.
        pilot_question: Pregunta directa del piloto (opcional).
        templates: Módulo prompt_templates con render().
        event_store: EventStore opcional para RAG.
        telemetry_frame: Frame de telemetría opcional para usar ticker.
        strategy_advice: Advice de estrategia opcional para datos de ticker.
        lmu_api: Módulo lmu_api opcional para datos adicionales de ticker.

    Returns:
        String del prompt completo renderizado.
    """
    context_dict: dict = {
        "snapshot": snapshot,
        "trigger_reason": trigger_reason,
    }
    if pilot_question:
        context_dict["pilot_question"] = pilot_question

    # Si hay telemetry_frame, usar ticker en vez de snapshot crudo
    if telemetry_frame is not None:
        ticker_data = _build_ticker_data(snapshot, telemetry_frame, strategy_advice, lmu_api)
        ticker_text = generate_ticker(ticker_data)
        context_dict["ticker_text"] = ticker_text
        context_dict.pop("snapshot", None)
    else:
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
    telemetry_frame: Optional[dict] = None,
    strategy_advice: Optional[dict] = None,
    lmu_api: Optional[Any] = None,
) -> str:
    """Construye prompt para pregunta directa del piloto con RAG y ticker."""
    context_dict: dict = {
        "snapshot": snapshot,
        "pilot_question": pilot_question,
    }
    if chat_history:
        context_dict["chat_history"] = chat_history

    # Si hay telemetry_frame, usar ticker en vez de snapshot crudo
    if telemetry_frame is not None:
        ticker_data = _build_ticker_data(snapshot, telemetry_frame, strategy_advice, lmu_api)
        ticker_text = generate_ticker(ticker_data)
        context_dict["ticker_text"] = ticker_text
        context_dict.pop("snapshot", None)
    else:
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
