# CrewChief-Style TTS Event System — Implementation Plan v4 (Hybrid)

> **Status:** in_progress (IMPLEMENTING)
> **Goal:** Replicate CrewChief's deterministic event architecture in Vantare using a HYBRID approach: create new infrastructure (AudioQueueManager, EventManager, SessionAdapter, VerbosityEngine) and wrap existing events to work with it. Preserve all existing event code and tests.
> **Commitment:** Feature flag `USE_LEGACY_TRIGGERS` allows rollback at any time.
> **Strategy:** Create new components + adapter layer. Existing events stay untouched. New components integrate with engine.py via feature flag.

---

## ADRs (Architectural Decisions)

### ADR-1: Hybrid Approach
**Decision:** Do NOT rewrite existing events. They already work with `evaluate(state) → List[AlertMessage]`. Create new infrastructure (AudioQueueManager, EventManager, SessionAdapter) and an **adapter layer** that wraps existing events to feed them into the new system.

**Rationale:**
- Existing events have 100+ tests and production logic
- Rewriting risks breaking working code
- New system can coexist via feature flag
- Adapter layer is thin (~50 lines per event max)

### ADR-2: TTS Pipeline (MVP)
**Decision (MVP):** Frontend continues to call `/tts` endpoint. Backend `AudioQueueManager` broadcasts `AlertMessage` with `text` via WebSocket. Frontend receives it, calls `/tts?text=...`, gets blob, enqueues in `audioQueue`.

**Future:** Backend `AudioQueueManager` calls `TTSService.generate_async(text)`, awaits blob, sends binary frames via WebSocket (MessagePack + metadata header + raw audio).

### ADR-3: Dual Queue System
`AudioQueueManager` has two heaps:
- **Immediate** (spotter, critical): `SoundType <= IMPORTANT` (0-2)
- **Regular** (normal alerts): `SoundType >= REGULAR` (3-4)

Priority ordering within each queue: higher `MessagePriority` value = plays first.

### ADR-4: Feature Flag
`backend/.env` variable `USE_LEGACY_TRIGGERS=true/false`.
- `true`: engine.py uses old trigger loop (triggers.py + events returning List[AlertMessage])
- `false`: engine.py uses new EventManager + AudioQueueManager

Both paths coexist during migration.

### ADR-5: Enum Serialization
All `IntEnum` values serialize as integers via Pydantic v2 default. Frontend compares with `Number(payload.field_name)` — never string comparison.

### ADR-6: Session/Phase Normalization
Create `SessionAdapter` that converts LMU session values (int 0-4, string "race"/"RACE") to canonical `SessionType` and `SessionPhase` enums. This adapter is the ONLY entry point for session data in the new system.

### ADR-7: Verbosity Engine
`VerbosityEngine` adjusts message filtering based on traffic density:
- FULL (0): all messages pass
- MED (5): only MEDIUM+ (priority >= 10)
- LOW (10): only HIGH+ (priority >= 15)
- SILENT (20): only CRITICAL (priority >= 20)

Updates every 1s, caches result.

### ADR-8: Keep Quiet Mode
Manual override that suppresses all non-critical messages. Only SPOTTER and CRITICAL pass. Clears both queues when activated.

### ADR-9: Event Evaluation Frequency & Cooldown Compensation
**Context:** CrewChiefV4 evaluates events every ~50ms (20Hz). Vantare evaluates at 0.5Hz (every 2s) via `strategy_sender_loop`.

**Decision:** Do NOT increase evaluation frequency. Existing event cooldowns (defined per-event-type in `RaceEvent.cooldowns`) already assume 0.5Hz evaluation. The existing cooldown values (measured in seconds) naturally compensate for the slower cycle — e.g., a 30s cooldown fires at most once every 15 evaluation cycles at 0.5Hz vs once every 600 cycles at 20Hz.

**Effect on EventManager:**
- `EventManager.trigger_all()` is called from `evaluate_cycle()` at 0.5Hz (same as legacy triggers)
- Inside each event, `reset_tick()` clears per-tick dedup before evaluation
- `can_fire()` checks per-type cooldown against `_last_fired` timestamp — works correctly regardless of evaluation frequency
- `is_message_still_valid()` is especially important at 0.5Hz because messages may be stale by the time they're evaluated (see Phase 4 EventAdapter)

**No change needed to `STRATEGY_POLL_RATE` (2.0s).** The existing cooldown system handles the frequency gap.

### ADR-10: Pearls of Wisdom (Motivational Interleaving)
**Context:** CrewChiefV4 interleaves motivational messages ("Pearls of Wisdom") between regular messages at configurable intervals. These are not race-critical but improve driver morale.

**Decision:** Defer to Phase 9 (post-MVP). The MVP will not include Pearls of Wisdom. Phase 9 adds a separate `PearlsOfWisdomEvent` that generates motivational messages based on race context (position change, overtake, clean lap) and interleaves them at the AudioQueueManager level.

---

## Phase 1: Core Data Models & Session Adapter

**Files:**
- Modify: `backend/src/models/messages.py`
- Create: `backend/src/intelligence/session_adapter.py`
- Create: `backend/tests/test_session_adapter.py`

### Step 1.1 — SessionAdapter

```python
# backend/src/intelligence/session_adapter.py
from enum import Enum

class SessionType(str, Enum):
    PRACTICE = "Practice"
    QUALIFY = "Qualify"
    RACE = "Race"
    HOTLAP = "HotLap"
    FORMATION = "Formation"

class SessionPhase(str, Enum):
    GREEN = "Green"
    COUNTDOWN = "Countdown"
    FINISHED = "Finished"

# LMU shared memory maps: 0=Practice, 1=Qualify, 2=Race, 3=HotLap, 4=Formation
_LMU_INT_MAP = {0: "Practice", 1: "Qualify", 2: "Race", 3: "HotLap", 4: "Formation"}
_LMU_STR_MAP = {
    "practice": "Practice", "practise": "Practice",
    "qualify": "Qualify", "qualifying": "Qualify", "qual": "Qualify",
    "race": "Race", "racing": "Race",
    "hotlap": "HotLap", "hot_lap": "HotLap",
    "formation": "Formation",
}

def normalize_session_type(raw) -> str:
    if isinstance(raw, int):
        return _LMU_INT_MAP.get(raw, "Race")
    if isinstance(raw, str):
        return _LMU_STR_MAP.get(raw.strip().lower(), "Race")
    return "Race"

def normalize_session_phase(raw_phase: str) -> str:
    """Derive session phase. Finished/checkered/chequered → Finished."""
    p = (raw_phase or "").strip().lower()
    if p in ("finished", "checkered", "chequered"):
        return "Finished"
    if p in ("countdown", "pre_race", "formation"):
        return "Countdown"
    return "Green"
```

### Step 1.2 — QueuedMessage + Enums in messages.py

Add to `backend/src/models/messages.py`:

```python
from enum import IntEnum
from pydantic import BaseModel, Field, field_serializer
import time

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

# Modify AlertMessage — add sound_type, priority. audio_priority kept as legacy entry field.
class AlertMessage(BaseMessage):
    """Alerta determinista instantánea del Spotter (20Hz) que no requiere LLM.
    
    NOTA: audio_priority es el campo legacy que los eventos existentes setean
    (como string "CRITICAL"/"HIGH"/str(4)/etc.). El EventAdapter lo normaliza
    a SoundType + MessagePriority. Los nuevos componentes del plan usan
    priority y sound_type directamente. El @field_serializer convierte
    los IntEnum a int para transporte JSON."""
    alert_id: str
    category: str
    message: str
    payload: Dict[str, Any] = Field(default_factory=dict)
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
```

### Step 1.3 — RaceEvent Base Class Enhancements

**FIX:** The existing `RaceEvent` base class (`backend/src/intelligence/events/base_event.py`) is missing three methods that the EventManager and EventAdapter rely on. Add them with default implementations that maintain backward compatibility.

Add to `backend/src/intelligence/events/base_event.py`:

```python
def is_applicable(self, session_type: str, session_phase: str) -> bool:
    """Override in subclass to restrict event to specific session types/phases.
    Default: always applicable. Subclasses can filter by checking session_type
    (e.g., only during Race) or session_phase (e.g., not when Finished)."""
    return True

def reset_session(self) -> None:
    """Reset all internal state when a new session begins.
    Override in subclass if event tracks per-session state (position, lap counters, etc.).
    Default clears cooldowns and fired-in-tick sets."""
    self._last_fired.clear()
    self._fired_in_tick.clear()

def is_message_still_valid(self, event_type: str, current_state: dict,
                           snapshot: Optional[dict] = None) -> bool:
    """Called by EventAdapter validator to check if a delayed/queued message is still relevant.
    Override in subclass for time-sensitive messages (e.g., overtake alerts that expire
    if the opponent changed). Default returns True (message remains valid)."""
    return True
```

These methods are already implemented in some subclasses:
- `reset_session()` — already in `PositionEvent`, `LapTimesEvent`, `RaceTimeEvent`, `SessionEndEvent`, `LapCounterEvent`, `CommonActionsEvent`. Adding to base class makes it available for all.

### Step 1.4 — Tests

```python
# backend/tests/test_session_adapter.py
def test_normalize_session_type_int():
    assert normalize_session_type(2) == "Race"
def test_normalize_session_type_str_lowercase():
    assert normalize_session_type("qualify") == "Qualify"
def test_normalize_session_type_unknown():
    assert normalize_session_type("unknown") == "Race"
def test_normalize_session_phase_finished():
    assert normalize_session_phase("checkered") == "Finished"
    assert normalize_session_phase("chequered") == "Finished"
    assert normalize_session_phase("finished") == "Finished"
def test_normalize_session_phase_green():
    assert normalize_session_phase("green") == "Green"
    assert normalize_session_phase("") == "Green"
def test_normalize_session_phase_countdown():
    assert normalize_session_phase("countdown") == "Countdown"
    assert normalize_session_phase("pre_race") == "Countdown"
```

---

## Phase 2: AudioQueueManager (Dual Queue)

**Files:**
- Create: `backend/src/services/audio_queue.py`
- Create: `backend/tests/test_audio_queue.py`

### Step 2.1 — AudioQueueManager

```python
# backend/src/services/audio_queue.py
import asyncio, heapq, logging, threading, time
from typing import Any, Callable, Dict, List, Optional
from src.models.messages import QueuedMessage, SoundType, MessagePriority, AlertMessage

logger = logging.getLogger("vantare.audio_queue")

class AudioQueueManager:
    def __init__(self, broadcast_callback=None) -> None:
        self._broadcast = broadcast_callback
        self._verbosity: int = 0
        self._keep_quiet: bool = False
        self._verbosity_min_priority = {0: 1, 5: 10, 10: 15, 20: 20}
        self._validators: Dict[str, Callable[[QueuedMessage, Dict[str, Any]], bool]] = {}
        self._immediate: List = []  # heap for urgent messages (protected by _lock)
        self._regular: List = []    # heap for normal messages (protected by _lock)
        self._lock: threading.Lock = threading.Lock()
        self._counter: int = 0
        self._latest_state: Dict[str, Any] = {}
        self._running: bool = False
        self._wake_event: asyncio.Event = asyncio.Event()  # FIX: event-driven wake, no polling

    def update_state(self, state: Dict[str, Any]) -> None:
        self._latest_state = state

    def register_validator(self, event_type: str,
                           validator: Callable[[QueuedMessage, Dict[str, Any]], bool]) -> None:
        self._validators[event_type] = validator

    def set_verbosity(self, level: int) -> None:
        self._verbosity = level

    def set_keep_quiet(self, enabled: bool) -> None:
        self._keep_quiet = enabled
        if enabled:
            with self._lock:
                self._immediate.clear()
                self._regular.clear()

    def enqueue(self, msg: QueuedMessage) -> None:
        """Enqueue a message and wake the consumer loop."""
        if self._keep_quiet and msg.sound_type not in (SoundType.SPOTTER, SoundType.CRITICAL):
            return
        min_p = self._verbosity_min_priority.get(self._verbosity, 1)
        if int(msg.priority) < min_p:
            return
        with self._lock:
            self._counter += 1
            entry = (-int(msg.priority), self._counter, msg)
            if msg.sound_type <= SoundType.IMPORTANT:
                heapq.heappush(self._immediate, entry)
            else:
                heapq.heappush(self._regular, entry)
        self._wake_event.set()  # FIX: wake consumer instead of polling

    def enqueue_alert(self, alert: AlertMessage) -> None:
        """Spotter express path: broadcast directly, bypass queue."""
        if self._broadcast:
            self._broadcast(alert)

    async def start(self) -> None:
        """Consumer loop — waits on asyncio.Event instead of polling."""
        self._running = True
        while self._running:
            try:
                await self._wake_event.wait()  # FIX: block until woken by enqueue()
                self._wake_event.clear()
                # Drain queue completely — no sleeps between messages
                while self._running:
                    msg = self._dequeue_next()
                    if msg is None:
                        break
                    if not self._validate(msg):
                        continue
                    # MVP: broadcast AlertMessage with text → frontend calls /tts
                    alert = AlertMessage(
                        event="alert", alert_id=msg.message_id, category=msg.event_type,
                        message=msg.text or "",
                        audio_priority=msg.priority.name,
                        priority=msg.priority, sound_type=msg.sound_type,
                        severity="CRITICAL" if msg.priority >= MessagePriority.CRITICAL else "INFO",
                        ttl=int(msg.ttl_seconds) or 15,
                        dismissable=msg.sound_type >= SoundType.REGULAR,
                        audio_file_id=msg.audio_file_id,
                        payload={"priority": int(msg.priority), "sound_type": int(msg.sound_type)},
                    )
                    if self._broadcast:
                        self._broadcast(alert)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("AudioQueue error: %s", e, exc_info=True)
                await asyncio.sleep(0.5)

    async def stop(self) -> None:
        """Stop the consumer loop. Wakes the event so wait() exits."""
        self._running = False
        self._wake_event.set()  # FIX: wake the loop so it sees _running=False
        with self._lock:
            self._immediate.clear()
            self._regular.clear()

    def _dequeue_next(self) -> Optional[QueuedMessage]:
        """Check both queues independently. Regular queue is checked even if immediate has future-due msg."""
        now = time.time()
        with self._lock:
            # Check immediate queue
            while self._immediate:
                neg_prio, order, msg = self._immediate[0]
                if msg.is_expired(now):
                    heapq.heappop(self._immediate)
                    continue
                if msg.is_due(now):
                    heapq.heappop(self._immediate)
                    return msg
                break
            # Check regular queue
            while self._regular:
                neg_prio, order, msg = self._regular[0]
                if msg.is_expired(now):
                    heapq.heappop(self._regular)
                    continue
                if msg.is_due(now):
                    heapq.heappop(self._regular)
                    return msg
                break
        return None

    def _validate(self, msg: QueuedMessage) -> bool:
        if msg.event_type and msg.event_type in self._validators:
            try:
                return self._validators[msg.event_type](msg, self._latest_state)
            except Exception as e:
                logger.warning("Validator error for %s: %s", msg.event_type, e)
        return True

    def interrupt(self, min_priority: SoundType = SoundType.SPOTTER) -> None:
        """Send audio_interrupt message. Uses BaseMessage not raw dict for broadcast compat."""
        from src.models.messages import BaseMessage
        if self._broadcast:
            class AudioInterrupt(BaseMessage):
                event: str = "audio_interrupt"
                min_priority: int
            self._broadcast(AudioInterrupt(event="audio_interrupt", min_priority=int(min_priority)))
```

### Step 2.2 — Tests

```python
# backend/tests/test_audio_queue.py
import pytest, time
from src.services.audio_queue import AudioQueueManager
from src.models.messages import QueuedMessage, SoundType, MessagePriority

def test_immediate_before_regular():
    mgr = AudioQueueManager()
    reg = QueuedMessage(message_id="r1", text="reg", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM)
    imm = QueuedMessage(message_id="i1", text="imm", sound_type=SoundType.IMPORTANT, priority=MessagePriority.HIGH)
    mgr.enqueue(reg); mgr.enqueue(imm)
    assert mgr._dequeue_next().message_id == "i1"

def test_higher_priority_first():
    mgr = AudioQueueManager()
    low = QueuedMessage(message_id="l1", text="low", sound_type=SoundType.IMPORTANT, priority=MessagePriority.LOW)
    high = QueuedMessage(message_id="h1", text="high", sound_type=SoundType.IMPORTANT, priority=MessagePriority.CRITICAL)
    mgr.enqueue(low); mgr.enqueue(high)
    assert mgr._dequeue_next().message_id == "h1"

def test_expired_discarded():
    mgr = AudioQueueManager()
    msg = QueuedMessage(message_id="e1", text="exp", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM,
                        ttl_seconds=0.1, created_at=time.time() - 1.0)
    mgr.enqueue(msg)
    assert mgr._dequeue_next() is None

def test_keep_quiet_filters_regular():
    mgr = AudioQueueManager(); mgr.set_keep_quiet(True)
    mgr.enqueue(QueuedMessage(message_id="r1", text="reg", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM))
    assert len(mgr._regular) == 0

def test_keep_quiet_allows_critical():
    mgr = AudioQueueManager(); mgr.set_keep_quiet(True)
    mgr.enqueue(QueuedMessage(message_id="c1", text="crit", sound_type=SoundType.CRITICAL, priority=MessagePriority.CRITICAL))
    assert len(mgr._immediate) == 1

def test_verbosity_medium_filters_low():
    mgr = AudioQueueManager(); mgr.set_verbosity(5)
    low = QueuedMessage(message_id="l1", text="low", sound_type=SoundType.REGULAR, priority=MessagePriority.LOW)
    med = QueuedMessage(message_id="m1", text="med", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM)
    mgr.enqueue(low); mgr.enqueue(med)
    assert len(mgr._regular) == 1
    assert mgr._regular[0][2].priority == MessagePriority.MEDIUM

def test_verbosity_low_filters_medium():
    mgr = AudioQueueManager(); mgr.set_verbosity(10)
    mgr.enqueue(QueuedMessage(message_id="m1", text="med", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM))
    assert len(mgr._regular) == 0

def test_validator_called_with_latest_state():
    mgr = AudioQueueManager()
    mgr.update_state({"fuel_remaining": 5.0})
    calls = []
    mgr.register_validator("test_type", lambda msg, state: calls.append(state.get("fuel_remaining")))
    msg = QueuedMessage(message_id="v1", text="val", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM, event_type="test_type")
    mgr.enqueue(msg)
    mgr._validate(mgr._dequeue_next())
    assert calls == [5.0]

def test_future_due_regular_not_blocked_by_immediate():
    mgr = AudioQueueManager()
    imm = QueuedMessage(message_id="i1", text="imm", sound_type=SoundType.IMPORTANT, priority=MessagePriority.CRITICAL,
                        due_time=time.time() + 60)
    reg = QueuedMessage(message_id="r1", text="reg", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM)
    mgr.enqueue(imm); mgr.enqueue(reg)
    popped = mgr._dequeue_next()
    assert popped is not None
    assert popped.message_id == "r1"

@pytest.mark.asyncio
async def test_start_stop():
    mgr = AudioQueueManager()
    task = asyncio.create_task(mgr.start())
    # Wake the loop by enqueuing, then stop
    mgr.enqueue(QueuedMessage(message_id="wake", text="wake", sound_type=SoundType.REGULAR, priority=MessagePriority.MEDIUM))
    await asyncio.sleep(0.01)  # Yield to let start() process the wake event
    await mgr.stop()
    await task
    assert mgr._running is False
```

---

## Phase 3: VerbosityEngine

**Files:**
- Create: `backend/src/intelligence/verbosity.py`
- Create: `backend/tests/test_verbosity.py`

### Step 3.1 — VerbosityEngine

```python
# backend/src/intelligence/verbosity.py
import time
from typing import Dict, Any

class VerbosityLevel:
    FULL = 0     # All priorities >=1 pass (BACKGROUND included)
    MED = 5      # Only >= MEDIUM (10) pass
    LOW = 10     # Only >= HIGH (15) pass
    SILENT = 20  # Only >= CRITICAL (20) pass

class VerbosityEngine:
    def __init__(self):
        self._level: int = VerbosityLevel.FULL
        self._next_update: float = 0.0
        self._enabled: bool = True

    def evaluate(self, telemetry: Dict[str, Any]) -> int:
        """Returns verbosity level based on traffic density. Update every 1s."""
        if not self._enabled:
            return VerbosityLevel.FULL
        now = time.monotonic()
        if now < self._next_update:
            return self._level
        self._next_update = now + 1.0

        speed = float(telemetry.get("speed", 0.0))
        if speed < 5.0:
            self._level = VerbosityLevel.FULL
            return self._level

        gap_ahead = float(telemetry.get("gap_ahead", 99.0))
        gap_behind = float(telemetry.get("gap_behind", 99.0))
        in_close = (0 < gap_ahead < 1.5) and (0 < gap_behind < 1.5)
        very_close = (0 < gap_ahead < 1.0) or (0 < gap_behind < 1.0)
        in_traffic = (0 < gap_ahead < 3.0) and (0 < gap_behind < 3.0)
        car_close = (0 < gap_ahead < 2.0) or (0 < gap_behind < 2.0)

        if in_close or very_close:
            self._level = VerbosityLevel.LOW
        elif in_traffic or car_close:
            self._level = VerbosityLevel.MED
        else:
            self._level = VerbosityLevel.FULL
        return self._level
```

### Step 3.2 — Tests

```python
# backend/tests/test_verbosity.py
def test_full_verbosity_when_open_track():
    from src.intelligence.verbosity import VerbosityEngine, VerbosityLevel
    engine = VerbosityEngine()
    assert engine.evaluate({"speed": 50, "gap_ahead": 10, "gap_behind": 10}) == VerbosityLevel.FULL

def test_low_verbosity_in_close_traffic():
    from src.intelligence.verbosity import VerbosityEngine, VerbosityLevel
    engine = VerbosityEngine()
    assert engine.evaluate({"speed": 50, "gap_ahead": 1.0, "gap_behind": 1.0}) == VerbosityLevel.LOW

def test_med_verbosity_in_traffic():
    from src.intelligence.verbosity import VerbosityEngine, VerbosityLevel
    engine = VerbosityEngine()
    assert engine.evaluate({"speed": 50, "gap_ahead": 2.5, "gap_behind": 2.5}) == VerbosityLevel.MED

def test_low_when_car_very_close():
    from src.intelligence.verbosity import VerbosityEngine, VerbosityLevel
    engine = VerbosityEngine()
    assert engine.evaluate({"speed": 50, "gap_ahead": 0.8, "gap_behind": 99}) == VerbosityLevel.LOW

def test_caches_for_1_second():
    from src.intelligence.verbosity import VerbosityEngine, VerbosityLevel
    engine = VerbosityEngine()
    engine._next_update = time.monotonic() + 10
    assert engine.evaluate({"speed": 50, "gap_ahead": 1.0, "gap_behind": 1.0}) == VerbosityLevel.FULL
```

---

## Phase 4: EventAdapter (The Bridge)

**Files:**
- Create: `backend/src/intelligence/event_adapter.py`
- Create: `backend/tests/test_event_adapter.py`

### Step 4.1 — EventAdapter

This is the KEY component that wraps existing `RaceEvent` instances and converts their `AlertMessage` outputs into `QueuedMessage` for the AudioQueueManager.

```python
# backend/src/intelligence/event_adapter.py
import logging
import time
from typing import Any, Dict, List, Optional
from src.intelligence.events.base_event import RaceEvent
from src.services.audio_queue import AudioQueueManager
from src.models.messages import AlertMessage, QueuedMessage, SoundType, MessagePriority

logger = logging.getLogger("vantare.event_adapter")

# FIX: audio_priority has TWO encoding schemes across the codebase:
#   - Semantic strings: "CRITICAL", "HIGH", "MEDIUM", "LOW" (fuel.py, engine.py, flags.py, etc.)
#   - Integer strings:  "4"=critical, "3"=high, "2"=medium, "1"=low (spotter.py, position.py, lap_times.py)
# _normalize_priority() handles both formats.

_INT_PRIORITY_MAP = {
    "4": (SoundType.CRITICAL, MessagePriority.CRITICAL),
    "3": (SoundType.IMPORTANT, MessagePriority.HIGH),
    "2": (SoundType.REGULAR, MessagePriority.MEDIUM),
    "1": (SoundType.REGULAR, MessagePriority.LOW),
}

_STR_PRIORITY_MAP = {
    "CRITICAL": (SoundType.CRITICAL, MessagePriority.CRITICAL),
    "HIGH": (SoundType.IMPORTANT, MessagePriority.HIGH),
    "MEDIUM": (SoundType.REGULAR, MessagePriority.MEDIUM),
    "LOW": (SoundType.REGULAR, MessagePriority.LOW),
    "SPOTTER": (SoundType.SPOTTER, MessagePriority.CRITICAL),
}

def _normalize_priority(audio_priority: str) -> tuple[SoundType, MessagePriority]:
    """Normalize both semantic and integer-string audio_priority values."""
    upper = audio_priority.strip().upper()
    # Try integer-string map first (e.g., "1", "2", "3", "4")
    result = _INT_PRIORITY_MAP.get(upper)
    if result:
        return result
    # Fall back to semantic-string map
    result = _STR_PRIORITY_MAP.get(upper)
    if result:
        return result
    logger.warning("Unknown audio_priority '%s', defaulting to REGULAR/MEDIUM", audio_priority)
    return (SoundType.REGULAR, MessagePriority.MEDIUM)

class EventAdapter:
    """Wraps existing RaceEvent instances to work with AudioQueueManager."""

    def __init__(self, audio_queue: AudioQueueManager) -> None:
        self.audio_queue = audio_queue

    def adapt_event(self, event: RaceEvent) -> None:
        """Register validators for all event types in this event's cooldowns."""
        for event_type in event.cooldowns:
            self.audio_queue.register_validator(
                event_type,
                lambda msg, state, et=event_type, ev=event:
                    self._validate_message(et, msg, state, ev)
            )

    def _validate_message(self, event_type: str, msg: QueuedMessage, state: Dict[str, Any], event: RaceEvent) -> bool:
        """Call event's is_message_still_valid if it exists, else True."""
        if hasattr(event, 'is_message_still_valid'):
            try:
                return event.is_message_still_valid(event_type, state, msg.session_data_snapshot)
            except Exception as e:
                logger.warning("Validator error for %s: %s", event_type, e)
        return True

    def process_event_output(self, event: RaceEvent, alerts: List[AlertMessage]) -> None:
        """Convert AlertMessages from an event into QueuedMessages and enqueue them."""
        for alert in alerts:
            queued = self._alert_to_queued(alert)
            if queued:
                self.audio_queue.enqueue(queued)

    def _alert_to_queued(self, alert: AlertMessage) -> Optional[QueuedMessage]:
        """Convert AlertMessage to QueuedMessage with proper priority mapping.
        Uses _normalize_priority() to handle both semantic and integer-string audio_priority values."""
        sound_type, priority = _normalize_priority(alert.audio_priority)
        return QueuedMessage(
            message_id=alert.alert_id,
            text=alert.message,
            audio_file_id=getattr(alert, 'audio_file_id', None),
            sound_type=sound_type,
            priority=priority,
            ttl_seconds=float(alert.ttl or 15),
            due_time=0.0,  # Immediate
            event_type=alert.event,
            session_data_snapshot=alert.payload if alert.payload else {},
            created_at=time.time(),
        )
```

### Step 4.2 — Tests

```python
# backend/tests/test_event_adapter.py
import time
from src.intelligence.event_adapter import EventAdapter
from src.services.audio_queue import AudioQueueManager
from src.models.messages import AlertMessage, QueuedMessage, SoundType, MessagePriority
from src.intelligence.events.fuel import FuelEvent

def test_adapter_converts_alert_to_queued():
    mgr = AudioQueueManager()
    adapter = EventAdapter(mgr)
    event = FuelEvent()
    alert = AlertMessage(
        event="estimate_1_lap",
        alert_id="test-id",
        category="fuel",
        message="Queda 1 vuelta.",
        audio_priority="HIGH",
        severity="HIGH",
        ttl=30,
        dismissable=True,
        payload={},
    )
    adapter.process_event_output(event, [alert])
    assert len(mgr._immediate) == 1
    msg = mgr._immediate[0][2]
    assert msg.sound_type == SoundType.IMPORTANT
    assert msg.priority == MessagePriority.HIGH
    assert msg.text == "Queda 1 vuelta."

def test_adapter_registers_validators():
    mgr = AudioQueueManager()
    adapter = EventAdapter(mgr)
    event = FuelEvent()
    adapter.adapt_event(event)
    assert "estimate_1_lap" in mgr._validators

def test_adapter_priority_mapping_semantic():
    mgr = AudioQueueManager()
    adapter = EventAdapter(mgr)
    for audio_prio, (expected_st, expected_prio) in {
        "CRITICAL": (SoundType.CRITICAL, MessagePriority.CRITICAL),
        "HIGH": (SoundType.IMPORTANT, MessagePriority.HIGH),
        "MEDIUM": (SoundType.REGULAR, MessagePriority.MEDIUM),
        "LOW": (SoundType.REGULAR, MessagePriority.LOW),
    }.items():
        alert = AlertMessage(
            event="test", alert_id="t", category="test", message="test",
            audio_priority=audio_prio, severity="INFO", ttl=10, dismissable=True, payload={}
        )
        q = adapter._alert_to_queued(alert)
        assert q.sound_type == expected_st, f"Semantic {audio_prio}: expected SoundType.{expected_st.name}"
        assert q.priority == expected_prio, f"Semantic {audio_prio}: expected MessagePriority.{expected_prio.name}"

def test_adapter_priority_mapping_integer_string():
    """FIX: spotter.py and position.py use integer strings '1'..'4' for audio_priority."""
    mgr = AudioQueueManager()
    adapter = EventAdapter(mgr)
    for audio_prio, (expected_st, expected_prio) in {
        "4": (SoundType.CRITICAL, MessagePriority.CRITICAL),
        "3": (SoundType.IMPORTANT, MessagePriority.HIGH),
        "2": (SoundType.REGULAR, MessagePriority.MEDIUM),
        "1": (SoundType.REGULAR, MessagePriority.LOW),
    }.items():
        alert = AlertMessage(
            event="test", alert_id="t", category="test", message="test",
            audio_priority=audio_prio, severity="INFO", ttl=10, dismissable=True, payload={}
        )
        q = adapter._alert_to_queued(alert)
        assert q.sound_type == expected_st, f"Int-string {audio_prio}: expected SoundType.{expected_st.name}"
        assert q.priority == expected_prio, f"Int-string {audio_prio}: expected MessagePriority.{expected_prio.name}"

def test_adapter_priority_unknown_defaults():
    mgr = AudioQueueManager()
    adapter = EventAdapter(mgr)
    alert = AlertMessage(
        event="test", alert_id="t", category="test", message="test",
        audio_priority="UNKNOWN", severity="INFO", ttl=10, dismissable=True, payload={}
    )
    q = adapter._alert_to_queued(alert)
    assert q.sound_type == SoundType.REGULAR
    assert q.priority == MessagePriority.MEDIUM
```

---

## Phase 5: EventManager + Engine Integration

**Files:**
- Create: `backend/src/intelligence/event_manager.py`
- Modify: `backend/src/config.py` (add `USE_LEGACY_TRIGGERS`)
- Modify: `backend/src/intelligence/engine.py`
- Modify: `backend/src/main.py` (lifespan: create AudioQueueManager, wire into engine, start consumer task)
- Create: `backend/tests/test_event_manager.py`

### Step 5.1 — EventManager

```python
# backend/src/intelligence/event_manager.py
import logging
from typing import Dict, Any, List, Optional
from src.intelligence.events.base_event import RaceEvent
from src.intelligence.events.fuel import FuelEvent
from src.intelligence.events.position import PositionEvent
from src.intelligence.events.lap_times import LapTimesEvent
from src.intelligence.events.race_time import RaceTimeEvent
from src.intelligence.events.pit_stops import PitStopsEvent
from src.intelligence.events.penalties import PenaltiesEvent
from src.intelligence.events.flags import FlagsEvent
from src.intelligence.events.damage import DamageEvent
from src.intelligence.events.engine import EngineEvent
from src.intelligence.events.conditions import ConditionsEvent
from src.intelligence.events.multiclass import MulticlassEvent
from src.intelligence.events.session_end import SessionEndEvent
from src.intelligence.events.tyres import TyreEvent
from src.intelligence.events.lap_counter import LapCounterEvent
from src.intelligence.events.common_actions import CommonActionsEvent
from src.services.audio_queue import AudioQueueManager
from src.intelligence.session_adapter import normalize_session_type, normalize_session_phase
from src.intelligence.event_adapter import EventAdapter
from src.intelligence.verbosity import VerbosityEngine

logger = logging.getLogger("vantare.event_manager")

class EventManager:
    def __init__(self, audio_queue: AudioQueueManager) -> None:
        self.audio_queue = audio_queue
        self.adapter = EventAdapter(audio_queue)
        self.verbosity_engine = VerbosityEngine()

        # Create all events (without broadcast_callback — adapter handles output)
        self.events: List[RaceEvent] = [
            FuelEvent(),
            PositionEvent(),
            LapTimesEvent(),
            RaceTimeEvent(),
            PitStopsEvent(),
            PenaltiesEvent(),
            FlagsEvent(),
            DamageEvent(),
            EngineEvent(),
            ConditionsEvent(),
            MulticlassEvent(),
            SessionEndEvent(),
            TyreEvent(),
            LapCounterEvent(),
            CommonActionsEvent(),
        ]

        # Register validators for each event
        for event in self.events:
            self.adapter.adapt_event(event)

        self._previous_state: Dict[str, Any] = {}

    def trigger_all(self, current_state: Dict[str, Any]) -> None:
        session_type = normalize_session_type(current_state.get("session_type"))
        session_phase = normalize_session_phase(current_state.get("session_phase", ""))

        # Update verbosity
        telemetry_dict = {k: v for k, v in current_state.items()
                         if k in ("speed", "gap_ahead", "gap_behind")}
        self.audio_queue.set_verbosity(self.verbosity_engine.evaluate(telemetry_dict))

        # Update state for validators
        self.audio_queue.update_state(current_state)

        # Trigger each event (FIX: reset_tick() clears per-tick dedup before evaluation)
        for event in self.events:
            if event.is_applicable(session_type, session_phase):
                try:
                    event.reset_tick()  # Clear _fired_in_tick for fresh evaluation cycle
                    alerts = event.evaluate(current_state)
                    self.adapter.process_event_output(event, alerts)
                except Exception as e:
                    logger.error("Event %s failed: %s", event.__class__.__name__, e, exc_info=True)

        # Update previous state
        self._previous_state = current_state.copy()

    def on_session_change(self) -> None:
        """Reset all event states and previous_state on new session."""
        self._previous_state = {}
        for event in self.events:
            event.reset_session()

    def set_broadcast_callback(self, callback) -> None:
        """Set broadcast callback on all events (for spotter express path)."""
        for event in self.events:
            if hasattr(event, 'broadcast_callback'):
                event.broadcast_callback = callback
```

### Step 5.2 — config.py addition

Add to `backend/src/config.py`:

```python
use_legacy_triggers: bool = Field(default=False, description="Use legacy trigger system instead of EventManager")
```

### Step 5.3 — engine.py integration

**FIX:** La firma de `__init__` en `backend/src/intelligence/engine.py` (línea 30) debe aceptar los nuevos parámetros. No se añade `start()` — la lógica de arranque va en `main.py`.

Modificar firma de `__init__` en `backend/src/intelligence/engine.py`:
```python
def __init__(
    self,
    live_context=None,
    context_builder=None,
    prompt_templates=None,
    llm_client=None,
    broadcaster=None,
    strategy_service=None,
    lmu_api=None,
    broadcast_callback=None,
    history_store=None,
    event_store=None,
    audio_queue=None,            # NUEVO
    use_legacy_triggers=False,   # NUEVO
) -> None:
```

Añadir dentro de `__init__`:
```python
self.use_legacy_triggers = use_legacy_triggers
self.audio_queue = audio_queue
self.event_manager = None
```

Modificar `evaluate_cycle()` para bifurcar según feature flag:

**IMPORTANTE:** El orden actual de `evaluate_cycle()` es: (1) conversión a dicts, (2) live_context, (3) pregunta del piloto, (4) triggers legacy. Los pasos 1-3 deben ejecutarse en AMBOS modos. Solo el paso 4 se bifurca.

```python
async def evaluate_cycle(self, telemetry_state, strategy_state, session_state=None, pilot_question=None) -> None:
    # [PASOS 1-2: conversión a dicts y live_context — igual para ambos modos]
    telemetry_dict = self._to_dict(telemetry_state)
    strategy_dict = self._to_dict(strategy_state)
    session_dict = self._to_dict(session_state)
    self.live_context.update_realtime(telemetry_dict, strategy_dict)
    # ... lap detection etc. ...

    # [PASO 3: pregunta del piloto — igual para ambos modos]
    if pilot_question:
        # ... (código existente sin cambios) ...
        return

    # [PASO 4: BIFURCACIÓN — legacy triggers vs EventManager]
    if self.use_legacy_triggers or not self.event_manager:
        # ... existing legacy trigger loop (sin cambios) ...
        pass
    else:
        # Nuevo path: EventManager + AudioQueueManager
        current_state = {**telemetry_dict, **strategy_dict, **session_dict}
        self.event_manager.trigger_all(current_state)
```

### Step 5.4 — main.py lifespan integration

**FIX:** La creación del engine está en `backend/src/main.py:108-112` dentro del lifespan handler, no en websocket.py. Hay que modificar el lifespan para crear AudioQueueManager y el EventManager.

Dentro del `lifespan` en `backend/src/main.py`, tras crear `strategy_service` y antes de crear `IntelligenceEngine`:

```python
from src.services.audio_queue import AudioQueueManager

# Crear AudioQueueManager (compartido entre engine y spotter)
audio_queue = AudioQueueManager(broadcast_callback=broadcast_sync)

# Instanciar IntelligenceEngine con los nuevos parámetros
intelligence_engine = IntelligenceEngine(
    broadcast_callback=broadcast_sync,
    history_store=history_store,
    event_store=event_store,
    audio_queue=audio_queue,
    use_legacy_triggers=settings.use_legacy_triggers,
)
app.state.intelligence_engine = intelligence_engine
app.state.audio_queue = audio_queue

# Si NO es legacy, crear EventManager y arrancar cola
if not settings.use_legacy_triggers:
    from src.intelligence.event_manager import EventManager
    event_manager = EventManager(audio_queue)
    intelligence_engine.event_manager = event_manager
    audio_queue_task = asyncio.create_task(audio_queue.start())
    app.state.audio_queue_task = audio_queue_task

# Pasar audio_queue al SpotterService para el express path
spotter_service.audio_queue = audio_queue
```

En el shutdown del lifespan, añadir:
```python
if hasattr(app.state, "audio_queue"):
    await app.state.audio_queue.stop()
if hasattr(app.state, "audio_queue_task"):
    app.state.audio_queue_task.cancel()
    try:
        await app.state.audio_queue_task
    except asyncio.CancelledError:
        pass
```

### Step 5.5 — Tests

Add to `backend/tests/test_event_manager.py`:

```python
# backend/tests/test_event_manager.py
import pytest
from src.intelligence.event_manager import EventManager
from src.services.audio_queue import AudioQueueManager
from src.models.messages import QueuedMessage, SoundType, MessagePriority

@pytest.fixture
def audio_queue():
    return AudioQueueManager()

@pytest.fixture
def event_manager(audio_queue):
    return EventManager(audio_queue)

def test_event_manager_initializes_all_events(event_manager):
    assert len(event_manager.events) == 15

def test_event_manager_trigger_all_enqueues_fuel_alert(event_manager):
    state = {
        "session_type": "Race",
        "session_phase": "Green",
        "fuel_remaining": 1.5,
        "fuel_capacity": 100.0,
        "fuel_per_lap": 3.0,
        "completed_laps": 10,
        "total_laps": 30,
        "in_pits": False,
        "session_id": "test-session",
    }
    event_manager.trigger_all(state)
    # Should have enqueued about_to_run_out or one_litre_remaining
    total = len(event_manager.audio_queue._immediate) + len(event_manager.audio_queue._regular)
    assert total > 0

def test_event_manager_session_change_resets_state(event_manager):
    event_manager.trigger_all({"session_type": "Race", "session_phase": "Green", "session_id": "s1"})
    event_manager.trigger_all({"session_type": "Race", "session_phase": "Green", "session_id": "s2"})
    # _previous_state should be updated
    assert event_manager._previous_state.get("session_id") == "s2"
```

---

## Phase 6: Spotter Express Path

**Files:**
- Modify: `backend/src/intelligence/spotter.py`

The spotter already has its own logic. We just need to ensure it can use `audio_queue.enqueue_alert()` for express path when the new system is active.

```python
# In spotter.py __init__:
def __init__(self, broadcast_callback=None, audio_queue: Optional[AudioQueueManager] = None) -> None:
    self.broadcast_callback = broadcast_callback
    self.audio_queue = audio_queue

# In evaluate_tick:
if alerts and self.audio_queue:
    for alert in alerts:
        self.audio_queue.enqueue_alert(alert)
elif alerts and self.broadcast_callback:
    for alert in alerts:
        self.broadcast_callback(alert)
```

---

## Phase 7: Frontend Priority Audio Queue

**Files:**
- Rewrite: `frontend/src/services/audioQueue.ts`
- Modify: `frontend/src/hooks/useWebSocket.ts`
- Modify: `frontend/src/App.tsx` (ya no necesita cambio — el overload legacy lo cubre, pero se lista para awareness)
- Modify: `frontend/src/__tests__/audioQueue.test.ts` (actualizar tests para ambas firmas)

### Step 7.1 — audioQueue.ts

```typescript
interface QueuedAudio {
  text?: string;
  url?: string;
  audioFileId?: string;
  soundType: number;   // 0=SPOTTER, 1=CRITICAL, 2=IMPORTANT, 3=REGULAR
  priority: number;    // 20=CRITICAL, 15=HIGH, 10=MEDIUM, 5=LOW
  ttl: number;
  messageId: string;
  createdAt: number;
}

class AudioQueue {
  private queue: QueuedAudio[] = [];
  private current: QueuedAudio | null = null;
  private audio: HTMLAudioElement | null = null;
  private onPlaybackChange: ((isPlaying: boolean) => void) | null = null;

  setOnPlaybackChange(cb: (isPlaying: boolean) => void): void { this.onPlaybackChange = cb; }

  /** Legacy overload: text+url → construye QueuedAudio internamente. Compatible con App.tsx y TTS flow existente. */
  enqueue(text: string, url: string): void;
  /** New API: objeto tipado con prioridad para el sistema de colas del plan. */
  enqueue(msg: QueuedAudio): void;
  enqueue(textOrMsg: string | QueuedAudio, url?: string): void {
    let msg: QueuedAudio;
    if (typeof textOrMsg === 'string') {
      // Legacy call from App.tsx (text submit) / useWebSocket.ts (TTS flow)
      msg = {
        text: textOrMsg,
        url: url!,
        soundType: 3,     // REGULAR
        priority: 10,     // MEDIUM
        ttl: 15,
        messageId: (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}_${Math.random().toString(36).slice(2)}`),
        createdAt: Date.now(),
      };
    } else {
      msg = textOrMsg;
    }

    // Expiry check
    if (msg.ttl > 0 && (Date.now() - msg.createdAt) > msg.ttl * 1000) return;

    // Interrupt if higher priority spotter/critical
    if (this.current && msg.soundType <= 1 && this.current.soundType > msg.soundType) {
      this.stopCurrent();
    }

    // Insert by priority descending
    const idx = this.queue.findIndex(q => q.priority < msg.priority);
    idx === -1 ? this.queue.push(msg) : this.queue.splice(idx, 0, msg);

    if (!this.current) this.playNext();
  }

  private stopCurrent(): void {
    if (this.audio) {
      this.audio.pause();
      this.audio.src = "";
      this.audio = null;
    }
    this.current = null;
  }

  private async playNext(): Promise<void> {
    const now = Date.now();
    this.queue = this.queue.filter(m => !(m.ttl > 0 && (now - m.createdAt) > m.ttl * 1000));
    if (this.queue.length === 0) {
      this.current = null;
      this.onPlaybackChange?.(false);
      return;
    }
    this.current = this.queue.shift()!;
    this.onPlaybackChange?.(true);

    if (this.current.audioFileId) {
      const played = await this.tryPlayLocal(this.current.audioFileId);
      if (played) return;
    }
    if (this.current.url) await this.playUrl(this.current.url);
  }

  private tryPlayLocal(audioFileId: string): Promise<boolean> {
    return new Promise(resolve => {
      const audio = new Audio(`/audio/${audioFileId}.wav`);
      this.audio = audio;
      audio.onended = () => { resolve(true); this.playNext(); };
      audio.onerror = () => { resolve(false); this.playNext(); };
      audio.play().catch(() => { resolve(false); this.playNext(); });
    });
  }

  private playUrl(url: string): Promise<void> {
    return new Promise(resolve => {
      const audio = new Audio(url);
      this.audio = audio;
      audio.onended = () => { resolve(); this.playNext(); };
      audio.onerror = () => { resolve(); this.playNext(); };
      audio.play().catch(() => { resolve(); this.playNext(); });
    });
  }

  clear(): void { this.stopCurrent(); this.queue = []; }
  get isPlaying(): boolean { return this.current !== null; }
}

export { AudioQueue };
export const audioQueue = new AudioQueue();
```

### Step 7.2 — useWebSocket.ts changes

```typescript
case "alert": {
  const payload = parsed.data || parsed;
  const msg: QueuedAudio = {
    text: payload.message,
    audioFileId: payload.audio_file_id,
    soundType: Number(payload.sound_type) ?? 3,
    priority: Number(payload.priority) ?? 10,
    ttl: payload.ttl || 15,
    messageId: payload.alert_id,
    createdAt: Date.now(),
  };
  audioQueue.enqueue(msg);
  break;
}
```

### Step 7.3 — Frontend tests (audioQueue.test.ts)

```typescript
// Tests actualizados para ambas firmas: legacy enqueue(text, url) y nueva enqueue(QueuedAudio)
import { AudioQueue } from "../services/audioQueue";

test("legacy enqueue(text, url) creates QueuedAudio with defaults", () => {
  const q = new AudioQueue();
  const queue = (q as any)["queue"] as any[];
  q.enqueue("test", "blob:http://test");
  expect(queue.length).toBe(1);
  const msg = queue[0];
  expect(msg.text).toBe("test");
  expect(msg.url).toBe("blob:http://test");
  expect(msg.soundType).toBe(3); // REGULAR default
  expect(msg.priority).toBe(10); // MEDIUM default
});

test("new enqueue(QueuedAudio) works with priority", () => {
  const q = new AudioQueue();
  const queue = (q as any)["queue"] as any[];
  q.enqueue({
    text: "Spotter alert",
    soundType: 0,  // SPOTTER
    priority: 20,  // CRITICAL
    ttl: 5,
    messageId: "spot-001",
    createdAt: Date.now(),
  });
  expect(queue.length).toBe(1);
  const msg = queue[0];
  expect(msg.soundType).toBe(0);
  expect(msg.priority).toBe(20);
});

test("higher priority inserted before lower", () => {
  const q = new AudioQueue();
  const queue = (q as any)["queue"] as any[];
  q.enqueue({ text: "low", soundType: 3, priority: 5, ttl: 10, messageId: "l1", createdAt: Date.now() });
  q.enqueue({ text: "high", soundType: 3, priority: 20, ttl: 10, messageId: "h1", createdAt: Date.now() });
  expect(queue[0].priority).toBe(20); // high first
  expect(queue[1].priority).toBe(5);  // low second
});

test("spotter interrupts current regular playback", () => {
  const q = new AudioQueue();
  const queue = (q as any)["queue"] as any[];
  q.enqueue({ text: "regular", soundType: 3, priority: 10, ttl: 10, messageId: "r1", createdAt: Date.now() - 1000 });
  // Spotter (soundType=0 <= 1) should stop current and insert at front
  q.enqueue({ text: "SPOTTER", soundType: 0, priority: 20, ttl: 5, messageId: "s1", createdAt: Date.now() });
  expect(queue.some(m => m.messageId === "s1")).toBe(true);
});

test("expired message discarded on playNext", () => {
  const q = new AudioQueue();
  const queue = (q as any)["queue"] as any[];
  q.enqueue({ text: "expired", soundType: 3, priority: 10, ttl: 1, messageId: "e1", createdAt: Date.now() - 5000 });
  const now = Date.now();
  const filtered = queue.filter(m => !(m.ttl > 0 && (now - m.createdAt) > m.ttl * 1000));
  expect(filtered.length).toBe(0);
});
```

---

## Phase 8: Keep Quiet Mode

**Files:**
- Modify: `frontend/src/store/appStore.ts`
- Modify: `backend/src/intelligence/engine.py`

Backend:
```python
async def handle_keep_quiet(self, enabled: bool) -> None:
    if self.audio_queue:
        self.audio_queue.set_keep_quiet(enabled)
    if self.broadcaster:
        self.broadcaster.send({"event": "keep_quiet", "enabled": enabled})
```

Frontend store:
```typescript
interface RadioState {
  keepQuiet: boolean;
}
setKeepQuiet: (enabled: boolean) => set(state => ({
  radio: { ...state.radio, keepQuiet: enabled }
}));
```

---

## Phase 9: Pearls of Wisdom (Motivational Interleaving)

**FIX:** CrewChiefV4 interleaves motivational messages ("Pearls of Wisdom" — GOOD/BAD/NEUTRAL) between regular messages. This is entirely absent from the plan. Add a dedicated event + interleaving support.

**Files:**
- Create: `backend/src/intelligence/events/pearls_of_wisdom.py`
- Create: `backend/tests/test_pearls_of_wisdom.py`

### Step 9.1 — PearlsOfWisdomEvent

```python
# backend/src/intelligence/events/pearls_of_wisdom.py
import logging
import random
import time
from typing import Any, Dict, List
from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage, SoundType, MessagePriority

logger = logging.getLogger("vantare.pearls")

# Motivational messages grouped by sentiment
_PEARLS_GOOD = [
    "¡Buena conducción! Sigue así.",
    "Ritmo excelente en esta vuelta.",
    "Buen adelantamiento, mantén la presión.",
    "Estás marcando tiempos competitivos.",
]
_PEARLS_BAD = [
    "Concéntrate, has perdido tiempo en ese sector.",
    "Cuidado con los errores, mantén la calma.",
    "Recupera el ritmo, puedes hacerlo mejor.",
]
_PEARLS_NEUTRAL = [
    "Respira hondo, mantén la concentración.",
    "Sigue el ritmo, la carrera es larga.",
    "Mantén la trazada limpia.",
]

class PearlsOfWisdomEvent(RaceEvent):
    """Generates interleaved motivational messages based on race context.
    CrewChiefV4: interleaves BEFORE/AFTER regular messages at configurable intervals."""

    def __init__(self, broadcast_callback=None) -> None:
        super().__init__(broadcast_callback=broadcast_callback)
        self.cooldowns = {"pearl": 120.0}  # Every 2 minutes max
        self._last_lap: int = 0
        self._last_position: int = 0
        self._clean_lap_streak: int = 0

    def reset_session(self) -> None:
        self._last_fired.clear()
        self._fired_in_tick.clear()
        self._last_lap = 0
        self._last_position = 0
        self._clean_lap_streak = 0

    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        if not self.can_fire("pearl", self.cooldowns.get("pearl", 120.0)):
            return alerts

        lap = state.get("completed_laps", 0) or state.get("lap_number", 0)
        position = state.get("position", 0) or state.get("race_position", 0)

        # Detect position improvement → GOOD pearl
        if self._last_position > 0 and position < self._last_position:
            msg = random.choice(_PEARLS_GOOD)
            alerts.append(self._create_alert(msg, SoundType.REGULAR, MessagePriority.LOW))
            self.mark_fired("pearl")
        # Detect new clean lap → NEUTRAL pearl (if streak > 3)
        elif lap > self._last_lap and self._clean_lap_streak >= 3:
            msg = random.choice(_PEARLS_NEUTRAL)
            alerts.append(self._create_alert(msg, SoundType.REGULAR, MessagePriority.LOW))
            self.mark_fired("pearl")
        # Random BAD pearl if position dropped (fallback)
        elif self._last_position > 0 and position > self._last_position:
            if random.random() < 0.3:  # 30% chance to avoid annoyance
                msg = random.choice(_PEARLS_BAD)
                alerts.append(self._create_alert(msg, SoundType.REGULAR, MessagePriority.LOW))
                self.mark_fired("pearl")

        self._last_lap = lap
        self._last_position = position
        if lap > self._last_lap:
            self._clean_lap_streak += 1
        else:
            self._clean_lap_streak = 0
        return alerts

    def _create_alert(self, message: str, sound_type: SoundType, priority: MessagePriority) -> AlertMessage:
        return AlertMessage(
            event="pearl",
            alert_id=f"pearl_{int(time.time())}",
            category="motivation",
            message=message,
            audio_priority=priority.name,
            severity="INFO",
            ttl=30,
            dismissable=True,
            payload={"sound_type": int(sound_type), "priority": int(priority)},
        )
```

### Step 9.2 — Register in EventManager

Add `PearlsOfWisdomEvent()` to the events list in `EventManager.__init__()`.

### Step 9.3 — Tests

```python
# backend/tests/test_pearls_of_wisdom.py
from src.intelligence.events.pearls_of_wisdom import PearlsOfWisdomEvent

def test_good_pearl_on_overtake():
    event = PearlsOfWisdomEvent()
    event._last_position = 5
    alerts = event.evaluate({"completed_laps": 10, "position": 3})
    assert len(alerts) == 1
    assert alerts[0].category == "motivation"

def test_no_pearl_within_cooldown():
    event = PearlsOfWisdomEvent()
    event.mark_fired("pearl")
    event._last_fired["pearl"] = time.time()
    alerts = event.evaluate({"completed_laps": 10, "position": 3})
    assert len(alerts) == 0

def test_neutral_pearl_after_clean_lap_streak():
    event = PearlsOfWisdomEvent()
    event._last_position = 3
    event._clean_lap_streak = 5
    event._last_fired.clear()
    alerts = event.evaluate({"completed_laps": 5, "position": 3})
    assert len(alerts) == 1

def test_reset_session_clears_state():
    event = PearlsOfWisdomEvent()
    event._clean_lap_streak = 5
    event._last_position = 3
    event.reset_session()
    assert event._clean_lap_streak == 0
    assert event._last_position == 0
```

---

## Phase 10: Pre-Recorded Audio Bridge

**Files:**
- Create: `docs/audio/ws-binary-protocol.md`

Document the binary WS protocol for future backend-side TTS:
1. Read 4 bytes as uint32 metadata_length
2. Read metadata_length bytes as MessagePack {sound_type, priority, message_id}
3. Read remaining bytes as audio_blob (WAV/MP3)
4. Create Blob → ObjectURL → audioQueue.enqueue({ url, sound_type, priority, ... })

No runtime code changes — just the interface contract.

---

## Implementation Order

```
Phase 1:  SessionAdapter + QueuedMessage + base_event enhancements + tests
Phase 2:  AudioQueueManager + tests (event-driven asyncio.Event, thread-safe)
Phase 3:  VerbosityEngine + tests
Phase 4:  EventAdapter (bridge with normalized priority for both semantic + int strings) + tests
Phase 5:  EventManager + config + engine.py __init__ + main.py lifespan wiring + tests
Phase 6:  Spotter express path (enqueue_alert bypass)
Phase 7:  Frontend priority queue (overload enqueue for legacy compat) + tests
Phase 8:  Keep quiet mode
Phase 9:  Pearls of Wisdom (motivational interleaving)
Phase 10: Pre-recorded bridge doc
```

## Success Criteria

1. All existing tests pass (290+ backend, 55+ frontend)
2. `USE_LEGACY_TRIGGERS=true` → old system runs untouched
3. `USE_LEGACY_TRIGGERS=false` → new event system runs with AudioQueueManager
4. AudioQueueManager respects priority ordering (immediate before regular)
5. VerbosityEngine filters correctly: MED→LOW(5) filtered, LOW→MEDIUM(10) filtered
6. `_dequeue_next` does NOT block regular queue when immediate has future-due msg
7. Spotter bypasses queue (express path via enqueue_alert)
8. Frontend compares `Number(payload.sound_type)` never string
9. Keep quiet suppresses non-critical messages
10. All 15 existing events work through EventAdapter without modification
11. **FIX:** SoundType enum matches CrewChiefV4 order (VOICE_RESPONSE=2, AUTO=5, OTHER=6)
12. **FIX:** `_normalize_priority()` handles both semantic strings (HIGH/MEDIUM/LOW) AND integer strings ("1"/"2"/"3"/"4") from spotter/position events
13. **FIX:** `RaceEvent` base class has `is_applicable()`, `reset_session()`, `is_message_still_valid()` methods
14. **FIX:** `EventManager.trigger_all()` calls `event.reset_tick()` before each evaluation
15. **FIX:** AudioQueueManager uses `threading.Lock` for all heap operations
16. **FIX:** AudioQueueManager uses `asyncio.Event` wake instead of polling (`asyncio.sleep(0.05)` eliminado)
17. **FIX:** `AudioQueueManager.stop()` llama a `_wake_event.set()` para despertar el consumer loop
18. **FIX:** `AudioQueueManager.interrupt()` envía `BaseMessage` tipado, no raw dict
19. **FIX:** Frontend `audioQueue.enqueue()` tiene overload para legacy `enqueue(text, url)` y nueva `enqueue(QueuedAudio)`
20. **FIX:** `AlertMessage.audio_priority` tiene default `"MEDIUM"` para compatibilidad con eventos que no lo setean
21. **FIX:** `IntelligenceEngine.__init__` acepta `audio_queue` y `use_legacy_triggers` como parámetros
22. **FIX:** Integración del sistema en `main.py` (lifespan), no en websocket.py
23. **FIX:** Spotter express path usa `audio_queue.enqueue_alert()` que llama al broadcast vía BaseMessage
