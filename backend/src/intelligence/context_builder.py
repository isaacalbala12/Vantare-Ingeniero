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


def build_prompt_for_question(
    snapshot: dict, 
    pilot_question: str, 
    chat_history: list = None,
    templates=None
) -> str:
    """Construye el prompt completo para una pregunta directa del piloto.
    
    A diferencia de build_prompt(), incluye el chat_history y usa el sistema
    de renderizado de prompt_templates para detectar telemetría automáticamente.
    """
    context_dict = {
        "snapshot": snapshot,
        "pilot_question": pilot_question
    }
    
    if chat_history:
        context_dict["chat_history"] = chat_history
    
    tier = "FAST"
    if snapshot.get("lap_number", 0) > 0 and (snapshot.get("speed") or snapshot.get("fuel")):
        tier = "STANDARD"
    if snapshot.get("weather_forecast"):
        tier = "DEEP"
    
    if templates is None:
        from src.intelligence import prompt_templates as templates
    return templates.render(context_dict, tier)
