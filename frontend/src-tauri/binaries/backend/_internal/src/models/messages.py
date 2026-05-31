import time
from enum import IntEnum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_serializer


class UIAction(BaseModel):
    """Acción táctica disparada por el LLM mediante Tool Calling para interactuar con la UI."""
    action_type: str  # e.g., "switch_dash_screen", "highlight_tyres", "show_pit_guide"
    params: Dict[str, Any] = Field(default_factory=dict)


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
    tier: str      # FAST, STD, DEEP


class AdviceTokenMessage(BaseMessage):
    """Envía un token individual de texto en tiempo real al piloto."""
    advice_id: str
    token: str


class AdviceEndMessage(BaseMessage):
    """Señaliza la finalización del stream de IA, incluyendo las acciones tácticas de UI parseadas."""
    advice_id: str
    full_text: str
    actions: List[UIAction] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Enums para el sistema de colas de audio CrewChief-style
# ---------------------------------------------------------------------------

class SoundType(IntEnum):
    """Lower value = more urgent, goes to immediate queue.
    Matches CrewChiefV4 SoundType order (SPOTTER=0, CRITICAL=1, VOICE_COMMAND_RESPONSE=2, IMPORTANT=3, REGULAR=4, AUTO=5, OTHER=6)."""
    SPOTTER = 0
    CRITICAL = 1
    VOICE_RESPONSE = 2    # CrewChiefV4: VOICE_COMMAND_RESPONSE=2 (between CRITICAL and IMPORTANT)
    IMPORTANT = 3
    REGULAR = 4
    AUTO = 5               # CrewChiefV4: AUTO=5 (system sounds, beeps)
    OTHER = 6              # CrewChiefV4: OTHER=6 (catch-all)


class MessagePriority(IntEnum):
    """Higher value = plays first within queue."""
    CRITICAL = 20
    HIGH = 15
    MEDIUM = 10
    LOW = 5
    BACKGROUND = 1


# ---------------------------------------------------------------------------
# Mensajes de alerta y cola
# ---------------------------------------------------------------------------

class AlertMessage(BaseMessage):
    """Alerta determinista instantánea del Spotter (20Hz) que no requiere LLM.

    NOTA: audio_priority es el campo legacy que los eventos existentes setean
    (como string "CRITICAL"/"HIGH"/str(4)/etc.). El EventAdapter lo normaliza
    a SoundType + MessagePriority. Los nuevos componentes del plan usan
    priority y sound_type directamente. El @field_serializer convierte
    los IntEnum a int para transporte JSON."""
    alert_id: str
    category: str  # e.g. "fuel", "tyres", "safety_car", "limiter", "gaps", "damage"
    message: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    # Campos extra para serialización correcta
    severity: str = "INFO"
    ttl: int = 10
    dismissable: bool = True
    # Legacy: usado solo por eventos existentes como entrada. Nueva fuente de verdad: priority + sound_type
    audio_priority: str = "MEDIUM"
    # Nuevos campos fuente de verdad para el sistema de colas
    sound_type: SoundType = SoundType.REGULAR
    priority: MessagePriority = MessagePriority.MEDIUM

    @field_serializer('sound_type', 'priority')
    def serialize_enum(self, value, _info):
        """Serialize IntEnum as int for JSON transport."""
        return value.value


class QueuedMessage(BaseModel):
    message_id: str
    text: Optional[str] = None
    audio_file_id: Optional[str] = None
    sound_type: SoundType = SoundType.REGULAR
    priority: MessagePriority = MessagePriority.MEDIUM
    ttl_seconds: float = 0.0
    due_time: float = 0.0
    event_type: str = ""
    session_data_snapshot: Optional[dict] = None
    created_at: float = 0.0

    def is_expired(self, now: Optional[float] = None) -> bool:
        if self.ttl_seconds <= 0:
            return False
        return ((now or time.time()) - self.created_at) > self.ttl_seconds

    def is_due(self, now: Optional[float] = None) -> bool:
        return (now or time.time()) >= self.due_time
