"""Construcción de prompts para el LLM con soporte RAG.

Toma el snapshot del tier adecuado, añade metadatos del trigger y la pregunta
del piloto si existe, y renderiza el prompt completo.

Si hay un EventStore configurado, inyecta los top-5 eventos históricos más
similares a la telemetría actual como contexto RAG.
"""

import logging
from typing import Any, Optional

from src.intelligence.ticker import generate_ticker

logger = logging.getLogger("vantare.context_builder")


def _build_ticker_data(
    snapshot: dict,
    telemetry_frame: Optional[dict] = None,
    strategy_advice: Optional[dict] = None,
    lmu_api: Optional[Any] = None,
) -> dict:
    """Construye el diccionario de datos para generate_ticker desde snapshot y fuentes adicionales.

    El dict resultante usa las keys que espera generate_ticker() de ticker.py.
    """
    data = {}
    # Posición (de telemetry_frame si disponible, fallback snapshot)
    if telemetry_frame:
        pos = telemetry_frame.get("standing_position", snapshot.get("position", snapshot.get("place", 0)))
    else:
        pos = snapshot.get("position", snapshot.get("place", 0))
    data["position"] = pos
    data["lap"] = snapshot.get("lap", 0)

    # Combustible (ticker espera "fuel", "fuel_rate_trend", "laps_rest")
    fuel_laps = 0
    fuel_rate = 0
    if strategy_advice:
        fuel_info = strategy_advice.get("fuel") or {}
        fuel_laps = fuel_info.get("estimated_laps_remaining", fuel_info.get("laps_left", 0))
        fuel_rate = fuel_info.get("fuel_rate_trend", 0)
    data["fuel"] = snapshot.get("fuel_in_tank", 0.0)
    data["fuel_rate_trend"] = fuel_rate
    data["laps_rest"] = fuel_laps

    # Neumáticos (ticker espera listas "tyre_wear" y "tyre_temps")
    wear_list, temps_list = [], []
    src = telemetry_frame if telemetry_frame else snapshot
    for wheel in ["fl", "fr", "rl", "rr"]:
        wear_list.append(src.get(f"tyre_wear_{wheel}", 0.0))
        temps_list.append(src.get(f"tyre_temp_{wheel}", 90.0))
    data["tyre_wear"] = wear_list
    data["tyre_temps"] = temps_list

    # Frenos (de REST API)
    brake_wear = [0, 0, 0, 0]
    if lmu_api is not None:
        try:
            brakes_data = lmu_api.get_additional_data("brakes")
            if isinstance(brakes_data, dict):
                bw = brakes_data.get("wear", [])
                if bw and len(bw) == 4:
                    brake_wear = [int(w * 100) for w in bw]
        except Exception as e:
            logger.debug("Error fetching brake wear from LMU API: %s", e)
    data["brake_wear"] = brake_wear

    # Gaps (de telemetry_frame o snapshot)
    ahead_gap = telemetry_frame.get("time_gap_place_ahead", snapshot.get("gap_ahead", 0)) if telemetry_frame else snapshot.get("gap_ahead", 0)
    behind_gap = telemetry_frame.get("time_gap_place_behind", snapshot.get("gap_behind", 0)) if telemetry_frame else snapshot.get("gap_behind", 0)
    data["ahead_gap"] = ahead_gap
    data["behind_gap"] = behind_gap

    # Rivales
    competitors = []
    if telemetry_frame:
        competitors = telemetry_frame.get("competitors", [])
    data["competitors"] = competitors
    data["total_cars"] = len(competitors)

    # Extraer nombres de rivales de competitors si no hay ahead_name/behind_name
    if competitors and len(competitors) > 0:
        comps_sorted = sorted(competitors, key=lambda c: c.get("gap", 999))
        # El más cercano detrás (gap positivo = detrás de ti)
        behind = [c for c in comps_sorted if c.get("gap", 0) > 0]
        # El más cercano adelante (gap negativo o menor que el tuyo... no tenemos posición aquí)
        # Simplificar: el de menor gap es el rival más cercano (adelante si gap negativo, detrás si positivo)
        data["behind_name"] = behind[0].get("name", "") if behind else ""
        data["ahead_name"] = ""  # No detectamos quién va adelante sin standing_position
    data["ahead_best"] = 0
    data["behind_best"] = 0
    data["delta"] = 0

    # Sesión
    data["session_class"] = telemetry_frame.get("session_class", "GT3") if telemetry_frame else "GT3"
    data["session_type"] = telemetry_frame.get("session_type", snapshot.get("phase", "RACE")) if telemetry_frame else snapshot.get("phase", "RACE")
    data["total_laps"] = telemetry_frame.get("session_laps_left", 0) if telemetry_frame else 0
    data["time_left"] = telemetry_frame.get("session_time_left", 0) if telemetry_frame else 0

    # Clima
    data["grip"] = snapshot.get("track_grip_level", 0)
    data["ambient_temp"] = snapshot.get("ambient_temp", 20)
    data["rain_chance"] = 0
    data["rain_min"] = 0
    data["safety_car_active"] = telemetry_frame.get("safety_car_active", False) if telemetry_frame else False
    data["cloud_coverage"] = snapshot.get("cloud_coverage", 0)
    data["raining"] = snapshot.get("raining", 0.0)
    data["avg_path_wetness"] = telemetry_frame.get("avg_path_wetness", 0.0) if telemetry_frame else 0.0
    data["track_temp"] = telemetry_frame.get("track_temp", 20) if telemetry_frame else 20

    # Otros
    data["speed"] = snapshot.get("speed", 0)
    data["drs_state"] = telemetry_frame.get("drs_state", False) if telemetry_frame else False
    data["pit_state"] = telemetry_frame.get("pit_state", 0) if telemetry_frame else 0
    data["battery_charge"] = snapshot.get("battery_charge", 100)
    data["player_best_lap"] = telemetry_frame.get("lap_time_best", 0) if telemetry_frame else 0

    return data


def _resolve_competitor_context(
    pilot_question: str,
    strategy_advice: Optional[dict],
) -> Optional[str]:
    """Pre-resuelve consultas de rivales por nombre en la pregunta del piloto."""
    if not pilot_question or not strategy_advice:
        return None
    competitors = strategy_advice.get("competitors") or []
    if not competitors:
        return None

    from src.intelligence.competitor_queries import CompetitorQuery, CompetitorQueryType, resolve_query
    from src.intelligence.driver_names import get_driver_by_partial
    import re

    match_driver = get_driver_by_partial(pilot_question, competitors)
    if not match_driver:
        for token in re.findall(r"[\w']+", pilot_question, flags=re.UNICODE):
            if len(token) >= 3:
                match_driver = get_driver_by_partial(token, competitors)
                if match_driver:
                    break
    if match_driver:
        result = resolve_query(
            CompetitorQuery(query_type=CompetitorQueryType.BY_NAME, name=match_driver.get("driver_name", "")),
            competitors,
        )
        if result.found:
            return result.summary
    return None


def _build_sector_context(strategy_service: Optional[Any] = None) -> Optional[str]:
    if strategy_service is None:
        return None
    try:
        from src.intelligence.sector_analysis import analyze_sectors, format_sector_analysis

        fuel = strategy_service.state.fuel
        track_length = strategy_service.track.track_length
        insights = analyze_sectors(
            fuel.delta_array_raw,
            fuel.delta_array_last,
            "Spa-Francorchamps",
            track_length,
        )
        text = format_sector_analysis(insights)
        return text or None
    except Exception:
        return None


def build_prompt(
    snapshot: dict,
    trigger_reason: str,
    pilot_question: Optional[str],
    templates: Any,
    event_store: Optional[Any] = None,
    telemetry_frame: Optional[dict] = None,
    strategy_advice: Optional[dict] = None,
    lmu_api: Optional[Any] = None,
    sweary: bool = False,
    strategy_service: Optional[Any] = None,
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
        "sweary": sweary,
    }
    if pilot_question:
        context_dict["pilot_question"] = pilot_question
        competitor_ctx = _resolve_competitor_context(pilot_question, strategy_advice)
        if competitor_ctx:
            context_dict["competitor_context"] = competitor_ctx

    sector_ctx = _build_sector_context(strategy_service)
    if sector_ctx:
        context_dict["sector_context"] = sector_ctx

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
    sweary: bool = False,
    strategy_service: Optional[Any] = None,
) -> str:
    """Construye prompt para pregunta directa del piloto con RAG y ticker."""
    context_dict: dict = {
        "snapshot": snapshot,
        "pilot_question": pilot_question,
        "sweary": sweary,
    }
    if chat_history:
        context_dict["chat_history"] = chat_history

    competitor_ctx = _resolve_competitor_context(pilot_question, strategy_advice)
    if competitor_ctx:
        context_dict["competitor_context"] = competitor_ctx
    sector_ctx = _build_sector_context(strategy_service)
    if sector_ctx:
        context_dict["sector_context"] = sector_ctx

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


def build_pilot_question_messages(
    snapshot: dict,
    pilot_question: str,
    chat_history: Optional[list] = None,
    templates: Optional[Any] = None,
    event_store: Optional[Any] = None,
    telemetry_frame: Optional[dict] = None,
    strategy_advice: Optional[dict] = None,
    lmu_api: Optional[Any] = None,
    sweary: bool = False,
    strategy_service: Optional[Any] = None,
) -> list:
    """Mensajes system+user para PTT/ask: ticker compacto, sin diccionario largo."""
    context_dict: dict = {
        "snapshot": snapshot,
        "pilot_question": pilot_question,
        "sweary": sweary,
    }
    if chat_history:
        context_dict["chat_history"] = chat_history

    competitor_ctx = _resolve_competitor_context(pilot_question, strategy_advice)
    if competitor_ctx:
        context_dict["competitor_context"] = competitor_ctx
    sector_ctx = _build_sector_context(strategy_service)
    if sector_ctx:
        context_dict["sector_context"] = sector_ctx

    if telemetry_frame is not None:
        ticker_data = _build_ticker_data(snapshot, telemetry_frame, strategy_advice, lmu_api)
        ticker_data["max_cls_rivals"] = 4
        ticker_text = generate_ticker(ticker_data)
        context_dict["ticker_text"] = ticker_text
    else:
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
    return templates.render_pilot_question_messages(context_dict, tier)


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
