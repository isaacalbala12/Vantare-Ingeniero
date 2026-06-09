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
from typing import Any, Dict, List

SYSTEM_PROMPT_BASIC = (
    "Eres el ingeniero de pista de un equipo de resistencia en Le Mans Ultimate. "
    "Hablas SOLO como ingeniero de pista: profesional, serio, 1-2 frases, estilo radio del muro de boxes. "
    "Responde ÚNICAMENTE a lo que pregunta el piloto; no añadas telemetría, estrategia ni estado de sesión "
    "si no lo pidió. Check de radio → confirma recepción en una frase, sin datos extra. "
    "Sin saludos innecesarios, sin repetir, sin comillas. No inventes datos que no estén en el contexto."
)

# System prompt con formato ticker embebido para el LLM.
# Incluye tabla diccionario que explica cada línea del ticker.
# Tamaño aproximado: ~800 tokens (system + formato + ticker + RAG).
SYSTEM_PROMPT_TICKER = """Eres el ingeniero de pista de un equipo de resistencia en Le Mans Ultimate. Profesional, serio y directo. Recibes datos en formato ticker compacto.

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

SWEARY_STYLE_HINT = (
    "\n\nESTILO: Puedes usar lenguaje colorido y directo de paddock cuando encaje con la situación."
)

CLEAN_STYLE_HINT = (
    "\n\nESTILO: Mantén un tono profesional y limpio, sin palabrotas ni vulgaridades."
)

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
                        "description": "El control visual o advertencia objetivo en el panel."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["blink_red", "show", "switch_to_regen_2"],
                        "description": "La acción visual o cambio de modo a ejecutar."
                    },
                    "duration_ms": {
                        "type": "integer",
                        "description": "Duración de la alerta en milisegundos."
                    }
                },
                "required": ["target", "action", "duration_ms"],
                "additionalProperties": False
            }
        }
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


SET_VERBOSITY_TOOL = {
    "type": "function",
    "function": {
        "name": "set_verbosity",
        "description": "Cambia el nivel de verbosidad del ingeniero (comentarios proactivos).",
        "parameters": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["silent", "normal", "detailed"],
                    "description": "silent=solo crítico+spotter; normal=medio+; detailed=todo.",
                },
            },
            "required": ["level"],
            "additionalProperties": False,
        },
    },
}


SET_BRAKING_ZONES_MUTE_TOOL = {
    "type": "function",
    "function": {
        "name": "set_braking_zones_mute",
        "description": (
            "Activa o desactiva silenciar TTS del ingeniero mientras el piloto frena fuerte. "
            "Usar cuando pide silencio en frenada o zonas de frenado."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "description": "True para silenciar comentarios NORMAL al frenar.",
                },
            },
            "required": ["enabled"],
            "additionalProperties": False,
        },
    },
}


SET_SPEAK_ONLY_TOOL = {
    "type": "function",
    "function": {
        "name": "set_speak_only",
        "description": (
            "Silencia o restaura comentarios proactivos del ingeniero. "
            "Usar cuando el piloto pide silencio, 'cállate', 'shhh', 'solo cuando te pregunte', "
            "o cuando quiere volver al modo normal."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "description": "True = solo hablar cuando el piloto pregunte; False = modo normal.",
                },
            },
            "required": ["enabled"],
            "additionalProperties": False,
        },
    },
}


GET_FUEL_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_fuel_status",
        "description": (
            "Consulta combustible restante (vueltas o litros). "
            "Usar cuando el piloto pregunta por gasolina, fuel, autonomía o cuántas vueltas le quedan."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


GET_GAP_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_gap_status",
        "description": (
            "Consulta gap con el coche de delante y/o detrás en segundos. "
            "Usar cuando pregunta por distancia, gap, quién va delante o detrás."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


GET_DAMAGE_REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "get_damage_report",
        "description": (
            "Informe de daños del coche (aero, pinchazos, piezas). "
            "Usar cuando pregunta por daños, estado del coche tras golpe, '¿estoy bien?'."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


GET_TIRE_WEAR_TOOL = {
    "type": "function",
    "function": {
        "name": "get_tire_wear",
        "description": (
            "Desgaste de neumáticos por eje. "
            "Usar cuando pregunta por neumáticos, gomas, desgaste, tyres."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


SET_PIT_FUEL_TOOL = {
    "type": "function",
    "function": {
        "name": "set_pit_fuel",
        "description": (
            "Configura litros de combustible en el menú de boxes (PitMenu LMU). "
            "Usar cuando pide añadir combustible en parada, ej. 'add 10 litres', 'pon 50 litros'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "litres": {
                    "type": "integer",
                    "description": "Litros mínimos deseados en la próxima parada.",
                },
            },
            "required": ["litres"],
            "additionalProperties": False,
        },
    },
}


SPOTTER_TOGGLE_TOOL = {
    "type": "function",
    "function": {
        "name": "spotter_toggle",
        "description": (
            "Activa o desactiva el spotter de proximidad. "
            "Usar para 'spot', 'espiar', 'don't spot', 'deja de espiar', silenciar spotter."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "description": "True = activar spotter; False = desactivar.",
                },
            },
            "required": ["enabled"],
            "additionalProperties": False,
        },
    },
}


GET_FLAG_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_flag_status",
        "description": "Estado de banderas (amarilla, SC, FCY). Usar si pregunta por bandera o safety car.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


GET_RACE_TIME_REMAINING_TOOL = {
    "type": "function",
    "function": {
        "name": "get_race_time_remaining",
        "description": "Tiempo o vueltas restantes de sesión/carrera.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


GET_PIT_WINDOW_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_pit_window_status",
        "description": "Estado de ventana de boxes (abierta/cerrada/próxima parada).",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


WATCH_SNIP_TOOL = {
    "type": "function",
    "function": {
        "name": "watch_snip",
        "description": "Marca rival para mensaje 'snip' / vigilancia activa (watch opponent).",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["snip", "clear"],
                    "description": "snip = vigilar rival activo; clear = quitar snip.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}


SET_PIT_TYRES_TOOL = {
    "type": "function",
    "function": {
        "name": "set_pit_tyres",
        "description": "Configura compound de neumáticos en menú boxes LMU.",
        "parameters": {
            "type": "object",
            "properties": {
                "compound": {"type": "string", "description": "Primary, Alternate, Wet, etc."},
                "confirm": {
                    "type": "boolean",
                    "description": "True solo tras confirmación explícita del piloto.",
                },
            },
            "required": ["compound"],
            "additionalProperties": False,
        },
    },
}


PILOT_PTT_TURN_TWO_PROMPT = (
    "Resume en 1-2 frases estilo radio lo que acabas de hacer para el piloto. "
    "Combina acción y datos si hubo varias tools. Sé breve."
)


PILOT_PTT_SYSTEM_PROMPT = """Eres el ingeniero de pista de un equipo de resistencia (Le Mans Ultimate): profesional, serio y breve.

El piloto habla por PTT; la transcripción puede ser imperfecta. Antes de responder en prosa:

1. Si pide cambiar tu comportamiento (silencio, verbosidad, frenada, pit menu, monitor rival) → tool de acción.
2. Si pide un dato concreto (fuel, gap, daños, neumáticos, rival) → tool de consulta. No inventes números.
3. Solo si es consejo abierto o estrategia sin dato concreto → responde sin tool (1-2 frases, estilo radio).
4. Responde solo a lo preguntado; no vuelques telemetría si no la pidieron.

Para acciones y consultas de estado DEBES usar tools. No simules la acción solo con texto."""


def get_pilot_ptt_tools(include_competitor_query: bool = True) -> List[Dict[str, Any]]:
    """Tools disponibles en el turno PTT (Task 13A/B/C)."""
    tools = [
        SET_SPEAK_ONLY_TOOL,
        SPOTTER_TOGGLE_TOOL,
        GET_FUEL_STATUS_TOOL,
        GET_GAP_STATUS_TOOL,
        GET_DAMAGE_REPORT_TOOL,
        GET_TIRE_WEAR_TOOL,
        SET_VERBOSITY_TOOL,
        SET_BRAKING_ZONES_MUTE_TOOL,
        SET_PIT_FUEL_TOOL,
        GET_FLAG_STATUS_TOOL,
        GET_RACE_TIME_REMAINING_TOOL,
        GET_PIT_WINDOW_STATUS_TOOL,
        WATCH_SNIP_TOOL,
        SET_PIT_TYRES_TOOL,
    ]
    if include_competitor_query:
        tools.append(COMPETITOR_QUERY_TOOL)
        tools.append(MONITOR_COMPETITOR_TOOL)
    return tools


def get_llm_tools(include_competitor_query: bool = True) -> List[Dict[str, Any]]:
    tools = list(UI_TOOLS)
    tools.append(SET_VERBOSITY_TOOL)
    tools.append(SET_BRAKING_ZONES_MUTE_TOOL)
    if include_competitor_query:
        tools.append(COMPETITOR_QUERY_TOOL)
        tools.append(MONITOR_COMPETITOR_TOOL)
    return tools


def _has_telemetry(context: dict) -> bool:
    """Detecta si el contexto tiene telemetría real de carrera (modo legacy)."""
    if not context:
        return False
    if _snapshot_has_telemetry(context.get("snapshot") or {}):
        return True
    lap = context.get("lap", 0) or context.get("lap_number", 0)
    speed = context.get("speed", 0)
    fuel = context.get("fuel", 0) or context.get("fuel_in_tank", 0)
    return lap > 0 and (speed > 0 or fuel > 0)


def _snapshot_has_telemetry(snapshot: dict) -> bool:
    if not snapshot:
        return False
    lap = snapshot.get("lap", 0) or snapshot.get("lap_number", 0)
    speed = snapshot.get("speed", 0)
    fuel = snapshot.get("fuel", 0) or snapshot.get("fuel_in_tank", 0)
    return lap > 0 and (speed > 0 or fuel > 0)


def _format_snapshot_compact(snapshot: dict) -> str:
    """Una línea de estado para PTT sin volcar JSON completo."""
    parts: list[str] = []
    lap = snapshot.get("lap_number") or snapshot.get("lap")
    if lap:
        parts.append(f"vuelta {lap}")
    pos = snapshot.get("position") or snapshot.get("place")
    if pos:
        parts.append(f"P{pos}")
    fuel = snapshot.get("fuel") or snapshot.get("fuel_in_tank")
    if fuel:
        parts.append(f"fuel {fuel}L")
    laps_rest = snapshot.get("fuel_laps_remaining")
    if laps_rest is not None:
        parts.append(f"~{float(laps_rest):.1f} vueltas restantes")
    gap_ahead = snapshot.get("gap_ahead")
    gap_behind = snapshot.get("gap_behind")
    if gap_ahead is not None and float(gap_ahead) < 99:
        parts.append(f"+{gap_ahead}s adelante")
    if gap_behind is not None and float(gap_behind) < 99:
        parts.append(f"-{gap_behind}s detrás")
    return " | ".join(parts)


def _has_ticker_text(context: dict) -> bool:
    """Detecta si el contexto usa ticker_text (modo nuevo)."""
    return "ticker_text" in context and context["ticker_text"]


def render_pilot_question_messages(context_dict: dict, tier: str) -> List[Dict[str, str]]:
    """PTT /ask: system + user con ticker compacto (sin diccionario de 800 tokens)."""
    style_hint = SWEARY_STYLE_HINT if context_dict.get("sweary") else CLEAN_STYLE_HINT
    system_content = f"{SYSTEM_PROMPT_BASIC}{style_hint}"

    user_sections: list[str] = []
    ticker_text = context_dict.get("ticker_text")
    if ticker_text:
        user_sections.append("Telemetría actual (ticker compacto):")
        user_sections.append(ticker_text)
    else:
        snapshot = context_dict.get("snapshot") or {}
        compact = _format_snapshot_compact(snapshot)
        if compact:
            user_sections.append(f"Estado: {compact}")

    rag_context = context_dict.get("rag_context")
    if rag_context:
        user_sections.append(f"Contexto reciente:\n{rag_context}")

    competitor_context = context_dict.get("competitor_context")
    if competitor_context:
        user_sections.append(f"Rival consultado:\n{competitor_context}")

    sector_context = context_dict.get("sector_context")
    if sector_context:
        user_sections.append(f"Sectores:\n{sector_context}")

    chat_history = context_dict.get("chat_history") or []
    if chat_history:
        hist_lines = [
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in chat_history[-4:]
            if msg.get("content")
        ]
        if hist_lines:
            user_sections.append("Historial breve:\n" + "\n".join(hist_lines))

    pilot_question = context_dict.get("pilot_question", "")
    if pilot_question:
        user_sections.append(f"Pregunta del piloto: {pilot_question}")

    user_content = "\n\n".join(user_sections) if user_sections else pilot_question
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


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
        payload = {k: v for k, v in context_dict.items() if k != "snapshot"}
        snapshot = context_dict.get("snapshot")
        if snapshot:
            payload["telemetry"] = snapshot
        context_json = json.dumps(payload, ensure_ascii=False, indent=2)
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