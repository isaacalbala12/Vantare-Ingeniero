import json
from typing import Any, Dict, List

SYSTEM_PROMPT = (
    "Eres el Ingeniero de Carrera de WEC. Sé extremadamente conciso, directo y estilo radio (máximo 2 frases). "
    "Prioriza la seguridad en pista; ante FCY o Safety Car, recomienda entrar a boxes inmediatamente."
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

def render(context_dict: dict, tier: str) -> str:
    """Devuelve el prompt completo: system prompt + contexto en JSON."""
    context_json = json.dumps(context_dict, ensure_ascii=False, indent=2)
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"### CONTEXTO DE TELEMETRÍA ({tier}) ###\n"
        f"{context_json}\n\n"
        f"INSTRUCCIÓN: Analiza los datos de carrera anteriores. Responde al piloto de forma ultra corta, clara y radio-style. "
        f"Si la telemetría lo requiere, activa la herramienta 'trigger_ui_alert'."
    )
