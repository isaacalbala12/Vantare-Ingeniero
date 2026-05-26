import json
from typing import Any, Dict, List

SYSTEM_PROMPT_WEC = (
    "Responde de forma concisa y directa."
)

SYSTEM_PROMPT_BASIC = (
    "Eres un ingeniero de carrera para Le Mans Ultimate. Sé conciso, directo y útil. "
    "Responde en 1-3 frases máximo. Estilo radio/comunicación de ingeniería."
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


def _has_telemetry(context: dict) -> bool:
    """Detecta si el contexto tiene telemetría real de carrera."""
    if not context:
        return False
    lap = context.get("lap", 0)
    speed = context.get("speed", 0)
    fuel = context.get("fuel", 0)
    return lap > 0 and (speed > 0 or fuel > 0)


def render(context_dict: dict, tier: str) -> str:
    """Devuelve el prompt completo: system prompt + contexto en JSON."""
    has_telemetry = _has_telemetry(context_dict)
    if has_telemetry:
        system_prompt = SYSTEM_PROMPT_WEC
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
