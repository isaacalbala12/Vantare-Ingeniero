import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


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


class AlertMessage(BaseMessage):
    """Alerta determinista instantánea del Spotter (20Hz) que no requiere LLM."""
    alert_id: str
    category: str  # e.g. "fuel", "tyres", "safety_car", "limiter", "gaps", "damage"
    message: str
    audio_priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    payload: Dict[str, Any] = Field(default_factory=dict)
    # Campos extra para serialización correcta
    severity: str = "INFO"
    ttl: int = 10
    dismissable: bool = True



# ==============================================================
# CrewChief V4 — Queue & Message System
# ==============================================================
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any, Callable
import time


class FragmentType:
    TEXT = "text"
    TIME = "time"
    OPPONENT = "opponent"
    INTEGER = "integer"
    PAUSE = "pause"


class Precision:
    AUTO_LAPTIMES = "AUTO_LAPTIMES"
    AUTO_GAPS = "AUTO_GAPS"
    SECONDS = "SECONDS"
    TENTHS = "TENTHS"
    HUNDREDTHS = "HUNDREDTHS"
    MINUTES = "MINUTES"


@dataclass
class TimeSpanWrapper:
    seconds: float
    precision: str = Precision.AUTO_LAPTIMES


@dataclass
class MessageFragment:
    type: str
    text: Optional[str] = None
    time_span: Optional[TimeSpanWrapper] = None
    opponent: Optional[str] = None
    integer: Optional[int] = None
    pause_ms: int = 0

    @staticmethod
    def text(p: str) -> "MessageFragment":
        return MessageFragment(FragmentType.TEXT, text=p)

    @staticmethod
    def time(s: float, p: str = Precision.AUTO_LAPTIMES) -> "MessageFragment":
        return MessageFragment(FragmentType.TIME, time_span=TimeSpanWrapper(s, p))

    @staticmethod
    def opponent(n: str) -> "MessageFragment":
        return MessageFragment(FragmentType.OPPONENT, opponent=n)

    @staticmethod
    def integer(v: int) -> "MessageFragment":
        return MessageFragment(FragmentType.INTEGER, integer=v)

    @staticmethod
    def pause(ms: int) -> "MessageFragment":
        return MessageFragment(FragmentType.PAUSE, pause_ms=ms)


@dataclass
class DelayedMessageEvent:
    method_name: str
    method_params: list
    event_instance: Any


_id_counter = 0


class QueuedMessage:
    def __init__(
        self,
        name: str,
        expires: float = 10.0,
        fragments: Optional[List] = None,
        alternate: Optional[List] = None,
        delay: float = 0.0,
        event: Any = None,
        validation: Optional[Dict] = None,
        priority: int = 5,
        sound_type: str = "REGULAR",
        trigger_fn: Optional[Callable] = None,
        delayed: Optional[DelayedMessageEvent] = None,
    ):
        global _id_counter
        _id_counter += 1
        self.id = _id_counter
        self.name = name
        self.expires = expires
        self.delay = delay
        self.fragments = fragments or []
        self.alternate = alternate
        self.event = event
        self.validation = validation
        self.priority = priority
        self.sound_type = sound_type
        self.trigger_fn = trigger_fn
        self.delayed = delayed
        self.created = time.time()
        self.due = self.created + delay
        self.expiry = self.created + expires if expires > 0 else 0
        self.can_play = True
        self.is_rant = False

    def is_expired(self, now: Optional[float] = None) -> bool:
        return self.expiry > 0 and (now or time.time()) >= self.expiry

    def is_due(self, now: Optional[float] = None) -> bool:
        return (now or time.time()) >= self.due

    def age(self) -> float:
        return time.time() - self.created

    def prepare_repeat(self):
        self.name = f"REPEAT_{self.name}"
        self.priority = 5
        self.sound_type = "VOICE_COMMAND"
        self.due = 0
        self.expiry = 0
        self.trigger_fn = None
        self.event = None
        self.validation = None
        self.delay = 0


def contents(*objs) -> List[MessageFragment]:
    result = []
    for o in objs:
        if o is None:
            result.append(None)
        elif isinstance(o, MessageFragment):
            result.append(o)
        elif isinstance(o, str):
            result.append(MessageFragment.text(o))
        elif isinstance(o, int):
            result.append(MessageFragment.integer(o))
        elif isinstance(o, float):
            result.append(MessageFragment.time(o))
        elif isinstance(o, TimeSpanWrapper):
            result.append(MessageFragment.time(o.seconds, o.precision))
    return result


def Pause(ms: int) -> MessageFragment:
    return MessageFragment(FragmentType.PAUSE, pause_ms=ms)
