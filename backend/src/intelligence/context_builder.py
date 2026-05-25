from typing import Any, Dict, Optional
from src.intelligence.prompt_templates import render

def build_prompt(snapshot: dict, trigger_reason: str, pilot_question: Optional[str], templates) -> str:
    """Toma el snapshot del tier adecuado, añade metadatos del trigger y pregunta del piloto si existe, y renderiza el prompt completo."""
    context_dict = {
        "snapshot": snapshot,
        "trigger_reason": trigger_reason
    }
    if pilot_question:
        context_dict["pilot_question"] = pilot_question

    tier = "FAST"
    if "tyre_compound" in snapshot:
        tier = "STANDARD"
    if "weather_forecast" in snapshot:
        tier = "DEEP"

    return templates.render(context_dict, tier)
