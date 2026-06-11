"""
Prompt templates para el LLM.

El sistema soporta dos modos:
- MODO TICKER (nuevo): Usa ticker_text en vez de snapshot JSON.
  Context dict incluye: ticker_text, rag_context, trigger_reason, pilot_question.
- MODO LEGACY: Usa json.dumps(context_dict) para backward compatibility.
  Detecta modo por la presencia de 'ticker_text' en el context_dict.

Límite de tokens: System prompt (~200) + ticker (~400) + RAG (~100) ≈ 700 tokens.
"""

import json
from typing import Any

SYSTEM_PROMPT_BASIC = (
    "Eres un ingeniero de carrera. Para preguntas técnicas de carrera, sé técnico y conciso. "
    "Para preguntas generales, responde normalmente sin añadir contexto innecesario. "
    "Máximo 2-3 frases. Estilo radio."
)

# System prompt con formato ticker embebido para el LLM.
# Incluye tabla diccionario que explica cada línea del ticker.
# Tamaño aproximado: ~800 tokens (system + formato + ticker + RAG).
SYSTEM_PROMPT_TICKER = """Eres un ingeniero de carrera. Recibes datos en formato ticker compacto.

FORMATO TICKER — Tabla Diccionario:
=============================

### DRV — Datos del piloto
DRV:P{pos}|L{vuelta}|F:{fuel}L/{consumo}({laps_rest})|TYR:{wFL}/{wFR}/{wRL}/{wRR}·{tFL}/{tFR}/{tRL}/{tRR}

| Código | Significado | Ejemplo |
|--------|-------------|---------|
| P{pos} | Posición en pista (1-based) | P3 |
| L{vuelta} | Vuelta actual | L26 |
| F:{fuel}L | Combustible en tanque (litros) | F:42.3L |
| {consumo} | Consumo promedio (L/vuelta) | 3.2 |
| ({laps_rest}) | Vueltas restantes estimadas | (13L) |
| TYR:{w}/... | Desgaste neumáticos 0-100% | 72/68/65/63 |
| ·{t}/... | Temperatura neumáticos °C | ·92/94/98/96 |

**Regla:** Si lap ≤ 3, se omite la sección TYR (desgaste no representativo).

### BRK — Desgaste de frenos
BRK:{wFL}/{wFR}/{wRL}/{wRR}

| Código | Significado | Ejemplo |
|--------|-------------|---------|
| {wFL}/{wFR}/{wRL}/{wRR} | Desgaste 0-100% (FL/FR/RL/RR) | 38/35/22/20 |

**Nota:** Si no hay datos de REST API, se omite la línea BRK completa.

### GAP — Diferencias con rivales
GAP>{ahead_name}:+{ahead_sec}·{ahead_best}|<{behind_name}:{behind_sec}·{behind_best}·d{delta}

| Código | Significado | Ejemplo |
|--------|-------------|---------|
| {ahead_name} | Nombre piloto adelante (3 chars) | VST |
| +{ahead_sec} | Gap con el de adelante (segundos) | +2.1 |
| {ahead_best} | Mejor tiempo del de adelante | 1:48.2 |
| {behind_name} | Nombre piloto detrás (3 chars) | ALO |
| -{behind_sec} | Gap con el de detrás (segundos) | -1.2 |
| {behind_best} | Mejor tiempo del de detrás | 1:47.9 |
| d{delta} | Diferencia de ritmo (tu best - su best) | d-0.3 |

**Omisión:** Si líder, se omite >. Si último, se omite <.

### SES — Información de sesión
SES:{clase}|{tipo}|{total}L|{tiempo_restante}

| Código | Significado | Ejemplo |
|--------|-------------|---------|
| {clase} | Clase: HY=Hypercar, GT3, LMP2, LMP3, GTE | HY |
| {tipo} | Tipo: RACE, QUALI, PRACTICE | RACE |
| {total}L | Vueltas totales de carrera | 38L |
| {tiempo_restante} | Tiempo restante (MM:SS) | 45:22 |

**Abreviaturas de clase:** HY=Hypercar, GT3, LMP2, LMP3, GTE
**Abreviaturas de sesión:** RACE, QUALI, PRACTICE, PRA1-4, Q1-4, WUP, TEST

### WTH — Clima y condiciones
WTH:{grip}|{temp}°|{rain}%+{min}|SC:{S/N}

| Código | Significado | Ejemplo |
|--------|-------------|---------|
| {grip} | Nivel agarre: GRN=Green, LOW, MED=Medium, HIG, SAT=Saturated | MED |
| {temp}° | Temperatura ambiente °C | 22° |
| {rain}% | Probabilidad de lluvia 0-100% | 30% |
| +{min} | Minutos hasta lluvia | +15m |
| SC:{S/N} | Safety Car activo: S= Sí, N= No | SC:N |

**Agarre pista:** GRN(0), LOW(1), MED(2), HIG(3), SAT(4)

### RIV — Rivales
RIV:{total} cars
CLS1({n}):{detalle}·{detalle}·...   -- Rivales gap < 5s
CLS2({n}):{detalle}·{detalle}·...   -- Rivales gap 5-30s
FAR({n}):{gap}s behind              -- Rivales gap > 30s
LAP({n}):{name}(-{n}L)·...          -- Rivales doblados

Formato detalle: {name}|{class}|{gap}|V{laps}
Ejemplo: VST|HY|+2.1|V22 · ALO|HY|-1.2|V22

=============================

Máximo 2-3 frases. Estilo radio. Técnico y conciso."""

SWEARY_STYLE_HINT = "\n\nESTILO: Puedes usar lenguaje colorido y directo de paddock cuando encaje con la situación."

CLEAN_STYLE_HINT = "\n\nESTILO: Mantén un tono profesional y limpio, sin palabrotas ni vulgaridades."

UI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "trigger_ui_alert",
            "description": "Dispara alertas visuales o cambia pantallas en el dashboard del piloto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": ["pit_button", "fuel_warning", "hybrid_map"],
                        "description": "El control visual o advertencia objetivo en el panel.",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["blink_red", "show", "switch_to_regen_2"],
                        "description": "La acción visual o cambio de modo a ejecutar.",
                    },
                    "duration_ms": {"type": "integer", "description": "Duración de la alerta en milisegundos."},
                },
                "required": ["target", "action", "duration_ms"],
                "additionalProperties": False,
            },
        },
    }
]

COMPETITOR_QUERY_TOOL = {
    "type": "function",
    "function": {
        "name": "query_competitor",
        "description": "Consulta datos de un rival: posición, gap, mejor vuelta, boxes.",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["by_name", "by_position", "by_class"],
                    "description": "Tipo de búsqueda del rival.",
                },
                "name": {
                    "type": "string",
                    "description": "Nombre o apellido del piloto (query_type=by_name).",
                },
                "position": {
                    "type": "integer",
                    "description": "Posición en clasificación (query_type=by_position).",
                },
                "driver_class": {
                    "type": "string",
                    "description": "Clase del coche: Hypercar, GT3, LMP2, etc. (query_type=by_class).",
                },
            },
            "required": ["query_type"],
            "additionalProperties": False,
        },
    },
}


MONITOR_COMPETITOR_TOOL = {
    "type": "function",
    "function": {
        "name": "monitor_competitor",
        "description": "Monitoriza un rival (max 3). Acciones: start o stop.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["start", "stop"]},
                "driver_index": {"type": "integer"},
            },
            "required": ["action", "driver_index"],
            "additionalProperties": False,
        },
    },
}


def get_llm_tools(include_competitor_query: bool = True) -> list[dict[str, Any]]:
    tools = list(UI_TOOLS)
    if include_competitor_query:
        tools.append(COMPETITOR_QUERY_TOOL)
        tools.append(MONITOR_COMPETITOR_TOOL)
    return tools


def _has_telemetry(context: dict) -> bool:
    """Detecta si el contexto tiene telemetría real de carrera (modo legacy)."""
    if not context:
        return False
    lap = context.get("lap", 0)
    speed = context.get("speed", 0)
    fuel = context.get("fuel", 0)
    return lap > 0 and (speed > 0 or fuel > 0)


def _has_ticker_text(context: dict) -> bool:
    """Detecta si el contexto usa ticker_text (modo nuevo)."""
    return "ticker_text" in context and context["ticker_text"]


def render(context_dict: dict, tier: str) -> str:
    """
    Devuelve el prompt completo: system prompt + contexto.

    Soporta dos modos:
    - MODO TICKER: context_dict contiene 'ticker_text'. Usa SYSTEM_PROMPT_TICKER
      con texto plano del ticker en vez de JSON.
    - MODO LEGACY: context_dict contiene 'lap', 'speed', 'fuel'. Usa json.dumps()
      para serializar el contexto como antes.

    Args:
        context_dict: Dict con contexto. Puede contener:
            - ticker_text (str): Texto ticker para modo nuevo
            - rag_context (str, opcional): Contexto histórico para RAG
            - trigger_reason (str): Razón del trigger
            - pilot_question (str, opcional): Pregunta del piloto
            - O en legacy: lap, speed, fuel, position, etc.
        tier: Nivel de detalle (FAST, STANDARD, DEEP)

    Returns:
        Prompt formateado para el LLM. Tamaño aproximado: ~800 tokens.
    """
    # Modo TICKER (nuevo)
    if _has_ticker_text(context_dict):
        ticker_text = context_dict["ticker_text"]
        trigger_reason = context_dict.get("trigger_reason", "")
        rag_context = context_dict.get("rag_context", "")
        pilot_question = context_dict.get("pilot_question", "")

        # Construir prompt con formato ticker
        sections = [SYSTEM_PROMPT_TICKER]
        if context_dict.get("sweary"):
            sections.append(SWEARY_STYLE_HINT)
        else:
            sections.append(CLEAN_STYLE_HINT)

        # Sección de telemetría en formato ticker
        sections.append("\n### TELEMETRÍA ###\n")
        sections.append(ticker_text)

        # Sección de contexto histórico (RAG)
        if rag_context:
            sections.append("\n### CONTEXTO HISTÓRICO ###\n")
            sections.append(rag_context)

        # Sección de trigger o pregunta
        if pilot_question:
            sections.append(f"\n### PREGUNTA DEL PILOTO ###\n{pilot_question}")
            competitor_context = context_dict.get("competitor_context")
            if competitor_context:
                sections.append(f"\n### DATOS RIVAL (consulta resuelta) ###\n{competitor_context}")
            sector_context = context_dict.get("sector_context")
            if sector_context:
                sections.append(f"\n### ANÁLISIS SECTORES ###\n{sector_context}")
        elif trigger_reason:
            sections.append(f"\n### MOTIVO ###\n{trigger_reason}")

        return "".join(sections)

    # Modo LEGACY (backward compatibility)
    has_telemetry = _has_telemetry(context_dict)
    if has_telemetry:
        system_prompt = SYSTEM_PROMPT_BASIC
        context_json = json.dumps(context_dict, ensure_ascii=False, indent=2)
        telemetry_section = (
            f"### CONTEXTO DE TELEMETRÍA ({tier}) ###\n"
            f"{context_json}\n\n"
            f"INSTRUCCIÓN: Analiza los datos de carrera anteriores. Responde al piloto de forma ultra corta, clara y radio-style. "
            f"Si la telemetría lo requiere, activa la herramienta 'trigger_ui_alert'."
        )
        return f"{system_prompt}\n\n{telemetry_section}"
    else:
        system_prompt = SYSTEM_PROMPT_BASIC
        pilot_question = context_dict.get("pilot_question", "")
        if pilot_question:
            return f"{system_prompt}\n\nPREGUNTA DEL PILOTO:\n{pilot_question}"
        else:
            return system_prompt


PILOT_QUESTION_SYSTEM = (
    "Eres el ingeniero de radio de Le Mans Ultimate (estilo WEC/F1). "
    "Responde en español, tono radio, directo. "
    "Responde SOLO a lo que pregunta el piloto: no recites telemetría no solicitada "
    "(temperaturas, lista de rivales, clima, desgaste) salvo que lo pida explícitamente. "
    "Saludos o small talk: UNA frase breve y humana, sin datos de pista. "
    "Preguntas técnicas: máximo 2 frases con las cifras relevantes. "
    "Usa únicamente datos del contexto; si falta un dato, dilo en una frase corta sin inventar."
)

PILOT_PTT_SYSTEM_PROMPT = (
    "Eres el ingeniero de radio de Le Mans Ultimate. El piloto habla por PTT. "
    "Elige la tool adecuada si la pregunta encaja; si es conversación abierta no uses tools."
)

PILOT_PTT_TURN_TWO_PROMPT = (
    "Resume en UNA frase corta estilo radio lo que acabas de hacer por el piloto."
)


def _tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


def get_pilot_ptt_tools(include_competitor_query: bool = True) -> list[dict[str, Any]]:
    tools = [
        _tool("set_speak_only", "Silenciar ingeniero hasta nueva pregunta o reactivar voz.", {"enabled": {"type": "boolean"}}, ["enabled"]),
        _tool("set_verbosity", "Cambiar verbosidad: silent, normal, detailed.", {"level": {"type": "string"}}, ["level"]),
        _tool("spotter_toggle", "Activar o desactivar spotter de proximidad.", {"enabled": {"type": "boolean"}}, ["enabled"]),
        _tool("get_fuel_status", "Consultar combustible / vueltas restantes.", {}),
        _tool("get_gap_status", "Consultar gap adelante y detrás.", {}),
        _tool("get_damage_report", "Informe de daños del monoplaza.", {}),
        _tool("get_tire_wear", "Desgaste de neumáticos por rueda.", {}),
        _tool("set_braking_zones_mute", "Silenciar alertas en zonas de frenada.", {"enabled": {"type": "boolean"}}, ["enabled"]),
        _tool("get_flag_status", "Estado de banderas / safety car.", {}),
        _tool("get_race_time_remaining", "Tiempo o vueltas restantes de sesión.", {}),
        _tool("get_pit_window_status", "Estado de ventana de boxes.", {}),
        _tool("watch_snip", "Vigilar rival activo (snip).", {"action": {"type": "string"}}, ["action"]),
        _tool("set_pit_fuel", "Configurar litros en menú de boxes.", {"litres": {"type": "number"}}, ["litres"]),
        _tool("set_pit_tyres", "Configurar compuesto en menú de boxes.", {"compound": {"type": "string"}}, ["compound"]),
        _tool("monitor_competitor", "Monitorizar rival por índice.", {"action": {"type": "string"}, "driver_index": {"type": "integer"}}, ["action", "driver_index"]),
    ]
    if include_competitor_query:
        tools.append(COMPETITOR_QUERY_TOOL)
    return tools


def render_pilot_question_messages(context_dict: dict, tier: str = "FAST") -> list[dict[str, str]]:
    """System + user messages for PTT free-form (sin tabla diccionario completa)."""
    pilot_question = context_dict.get("pilot_question", "")
    user_parts: list[str] = []
    ptt_context = context_dict.get("ptt_context")
    ticker_text = context_dict.get("ticker_text")
    snapshot = context_dict.get("snapshot") or {}
    if ptt_context:
        user_parts.append(f"Contexto:\n{ptt_context}")
    elif ticker_text:
        user_parts.append(f"Telemetría:\n{ticker_text}")
    elif snapshot:
        lap = snapshot.get("lap_number") or snapshot.get("lap") or 0
        pos = snapshot.get("place") or snapshot.get("position") or snapshot.get("standing_position") or "?"
        fuel = snapshot.get("fuel_in_tank") or snapshot.get("fuel") or "?"
        user_parts.append(f"Resumen: vuelta {lap}, P{pos}, fuel {fuel}L.")
    if pilot_question:
        user_parts.append(f"Pregunta del piloto: {pilot_question}")
    style = SWEARY_STYLE_HINT if context_dict.get("sweary") else CLEAN_STYLE_HINT
    system = f"{PILOT_QUESTION_SYSTEM}\n{style}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(user_parts) if user_parts else pilot_question},
    ]
