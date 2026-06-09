import time
from typing import Any

from pydantic import BaseModel, Field


class UIAction(BaseModel):
    """Acción táctica disparada por el LLM mediante Tool Calling para interactuar con la UI."""

    action_type: str  # e.g., "switch_dash_screen", "highlight_tyres", "show_pit_guide"
    params: dict[str, Any] = Field(default_factory=dict)


class BaseMessage(BaseModel):
    """Clase base para todos los mensajes WebSocket del Ingeniero de IA."""

    event: str
    timestamp: float = Field(default_factory=time.time)


class LLMPendingMessage(BaseMessage):
    """Notifica al piloto que un trigger de IA está procesando y llamando al LLM en background."""

    advice_id: str
    trigger_name: str
    priority: str  # CRITICAL, HIGH, MEDIUM, LOW


class AdviceStartMessage(BaseMessage):
    """Marca el inicio del streaming de tokens de respuesta del LLM."""

    advice_id: str
    tier: str  # FAST, STD, DEEP


class AdviceTokenMessage(BaseMessage):
    """Envía un token individual de texto en tiempo real al piloto."""

    advice_id: str
    token: str


class AdviceEndMessage(BaseMessage):
    """Señaliza la finalización del stream de IA, incluyendo las acciones tácticas de UI parseadas."""

    advice_id: str
    full_text: str
    actions: list[UIAction] = Field(default_factory=list)


class AlertMessage(BaseMessage):
    """Alerta determinista instantánea del Spotter (20Hz) que no requiere LLM."""

    alert_id: str
    category: str  # e.g. "fuel", "tyres", "safety_car", "limiter", "gaps", "damage"
    message: str
    audio_priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    payload: dict[str, Any] = Field(default_factory=dict)
    # Campos extra para serialización correcta
    severity: str = "INFO"
    ttl: int = 10
    dismissable: bool = True
