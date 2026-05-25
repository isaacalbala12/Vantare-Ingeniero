# Plan de Robustez — Ingeniero de IA

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar bugs críticos y estabilizar el flujo PTT del Ingeniero de IA.

**Architecture:** 4 fases ordenadas por dependencias. Fase 0 son parches rápidos independientes. Fase 1 elimina el Dual Path (causa raíz del bug de preemption). Fase 2 robustece el engine. Fase 3 son mejoras de infraestructura. Cada fase produce un estado funcional y desplegable.

**Tech Stack:** FastAPI, React/Zustand, Tauri, PyInstaller, CrofAI, Piper TTS.

---

## File Map

| Archivo | Rol | Cambios |
|---|---|---|
| `frontend/src/App.tsx` | Orquestador PTT + HTTP/WS | F1: eliminar fetch /ask. F0: timeout en fetch. F2: cola TTS |
| `frontend/src/hooks/useWebSocket.ts` | WS manager + message handler | F1: manejar advice_end con añadido al historial |
| `frontend/src/store/config.ts` | Zustand store | F0: selectores finos en store |
| `frontend/src/components/RadioOverlay.tsx` | Dashboard | F0: selectores finos individuales |
| `frontend/src/services/api.ts` | API calls | F0: timeout en getHealth |
| `frontend/src/store/config.ts` | Config validation | F0: validación en save |
| `backend/src/routers/websocket.py` | WS endpoint + pilot_question handler | F1: manejar respuesta del engine vía WS |
| `backend/src/routers/llm.py` | /ask endpoint | F1: simplificar, quitar TTS |
| `backend/src/routers/tts.py` | NUEVO: /tts endpoint | F1: endpoint separado de TTS |
| `backend/src/intelligence/engine.py` | Orquestador de triggers + LLM | F2: proteger piloto de preemption. F0: barrera arranque |
| `backend/src/intelligence/llm_client.py` | Cliente LLM (CrofAI via OpenAI SDK) | F0: timeout explícito. F3: unificar prompt |
| `backend/src/intelligence/triggers.py` | 12 triggers de carrera | F2: protección time jump. F0: fuel simulated fix |
| `backend/src/services/lmu_api.py` | Poller REST de LMU | F3: cache con TTL |
| `backend/src/services/llm_service.py` | SEGUNDO cliente LLM | F3: eliminar, unificar en llm_client.py |
| `backend/src/main.py` | Lifespan + setup | F2: barrera de sincronización en arranque |
| `backend/src/transport/broadcaster.py` | Wrapper de broadcast | F3: logging con advice_id |

---

## Phase 0: Quick Fixes (independientes, bajo riesgo)

### Task 0.1: Timeout en fetch del frontend

**Files:**
- Modify: `frontend/src/App.tsx:211`
- Modify: `frontend/src/services/api.ts:39`

**Detail:** El `fetch` a `/ask` y `/health` no tienen `AbortController`. Si el backend cuelga, la UI se congela.

**Changes in `frontend/src/App.tsx` — añadir timeout a la llamada /ask:**

```typescript
// Reemplazar el bloque try dentro de handlePTTEnd (línea ~206)
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout

try {
  const configState = useAppStore.getState().config;
  const baseUrl = `http://${configState.vllmIP || "localhost"}:${configState.serverPort || 8008}`;
  
  // ... chatHistory construction ...
  
  setRadioMode("SPEAKING_ENGINE");
  setCurrentTokens("");

  const response = await fetch(`${baseUrl}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: questionText, chat_history: chatHistory }),
    signal: controller.signal,
  });
  clearTimeout(timeoutId);
  // ... resto del handler ...
} catch (err) {
  clearTimeout(timeoutId);
  if (err instanceof DOMException && err.name === 'AbortError') {
    console.error("[App] Timeout: el backend no respondió en 15s");
  } else {
    console.error("[App] Falló la comunicación con el backend:", err);
  }
  setRadioMode("IDLE");
  setCurrentTokens("");
}
```

**Changes in `frontend/src/services/api.ts` — añadir timeout a getHealth:**

```typescript
export async function getHealth(): Promise<HealthResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);
  try {
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timeoutId);
    // ... resto igual ...
  } catch (err) {
    clearTimeout(timeoutId);
    // ... resto igual ...
  }
}
```

### Task 0.2: Timeout explícito en VLLMClient

**Files:**
- Modify: `backend/src/intelligence/llm_client.py:42-46`

**Detail:** El SDK de OpenAI no tiene timeout configurado. Si CrofAI se cuelga, la tarea de engine queda bloqueada para siempre.

**Change:**

```python
def _get_client(self) -> AsyncOpenAI:
    if self._client is None:
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=httpx.Timeout(25.0, connect=10.0, read=20.0),
            max_retries=1,
        )
    return self._client
```

Añadir import: `import httpx` al inicio del archivo (si no está ya).

### Task 0.3: Selectores finos en Zustand (rendimiento 20Hz)

**Files:**
- Modify: `frontend/src/components/RadioOverlay.tsx:11`
- No modify: `frontend/src/store/config.ts` (la store ya soporta selectores)

**Detail:** `RadioOverlay.tsx` se suscribe a todo el store con `const { radio, telemetry } = useAppStore()`. Esto re-renderiza cada 50ms aunque el chat no haya cambiado.

**Change in `RadioOverlay.tsx`:**

```typescript
// Antes (línea 11):
// const { radio, telemetry } = useAppStore();

// Después — selectores individuales que solo re-renderizan cuando cambia su slice:
const mode = useAppStore((s) => s.radio.mode);
const currentTokens = useAppStore((s) => s.radio.currentTokens);
const latestAdvice = useAppStore((s) => s.radio.latestAdvice);
const messageHistory = useAppStore((s) => s.radio.messageHistory);
const speed = useAppStore((s) => s.telemetry.speed ?? 0);
const gear = useAppStore((s) => s.telemetry.gear ?? 0);
const fuel = useAppStore((s) => s.telemetry.fuel ?? 0.0);
const lap = useAppStore((s) => s.telemetry.lap ?? 1);
const position = useAppStore((s) => s.telemetry.position ?? 1);
const gapAhead = useAppStore((s) => s.telemetry.gaps?.ahead ?? 0.0);

// Luego usar las variables directamente en lugar de desestructurar radio/telemetry
```

### Task 0.4: Validación de configuración

**Files:**
- Modify: `frontend/src/components/ConfigPanel.tsx:166-194`

**Detail:** El botón GUARDAR no valida IP, puerto ni hotkey antes de persistir.

**Change — añadir validación al inicio de handleSaveSettings:**

```typescript
const handleSaveSettings = () => {
  // Validar IP
  const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$|^localhost$|^[a-zA-Z0-9.-]+$/;
  if (!vllmIP.trim() || !ipRegex.test(vllmIP.trim())) {
    setSaveStatus("IP inválida");
    setTimeout(() => setSaveStatus(null), 2000);
    return;
  }
  // Validar puerto
  const port = Number(serverPort);
  if (isNaN(port) || port < 1 || port > 65535) {
    setSaveStatus("Puerto inválido (1-65535)");
    setTimeout(() => setSaveStatus(null), 2000);
    return;
  }
  // Validar hotkey (formato básico: Modificador+Tecla)
  const hotkeyParts = pttHotkey.split('+');
  if (hotkeyParts.length < 2) {
    setSaveStatus("Hotkey debe incluir modificador (ej: Ctrl+Shift+P)");
    setTimeout(() => setSaveStatus(null), 2000);
    return;
  }
  // ... resto del save igual ...
};
```

### Task 0.5: Pausar engine sin clientes conectados

**Files:**
- Modify: `backend/src/routers/websocket.py:84-122` (strategy_sender_loop)

**Detail:** El engine ejecuta triggers cada 2s aunque no haya nadie conectado. En modo offline simulado, los triggers se disparan cíclicamente y llaman a CrofAI sin necesidad.

**Change in strategy_sender_loop:**

```python
async def strategy_sender_loop(websocket: WebSocket, app_state) -> None:
    strategy_service = getattr(app_state, "strategy_service", None)
    if not strategy_service:
        logger.warning("Strategy service not found in app state")
        return

    last_advice_dict = None

    while True:
        try:
            # Saltar ciclo si no hay clientes conectados escuchando
            if not manager.active_connections:
                await asyncio.sleep(2.0)
                continue

            advice = strategy_service.get_latest_advice()
            # ... resto igual ...
```

### Task 0.6: Barrera de sincronización en arranque

**Files:**
- Modify: `backend/src/services/strategy_service.py:67-73` (método start)
- Modify: `backend/src/main.py:lifespan` (orden de inicialización)

**Detail:** El `IntelligenceEngine` necesita al menos un frame de telemetría antes de evaluar triggers. Añadir un `Event` de asyncio que se señalice cuando el primer ciclo de estrategia se complete.

**Change in `strategy_service.py` — añadir Event:**

```python
class StrategyService:
    def __init__(self, reader: TelemetryReader) -> None:
        # ... campos existentes ...
        self._ready_event = asyncio.Event()

    def start(self) -> None:
        if self._loop_task is not None:
            return
        self._loop_task = asyncio.create_task(self._run_loop())
        logger.info("StrategyService loop started")

    async def wait_until_ready(self, timeout: float = 10.0) -> bool:
        """Espera hasta que el primer ciclo de estrategia se complete."""
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning("StrategyService no estuvo listo en %fs", timeout)
            return False

    def _process_cycle(self) -> None:
        # ... código existente ...
        # Al final de _process_cycle, señalizar ready:
        if not self._ready_event.is_set():
            self._ready_event.set()
```

**Change in `main.py` — esperar a que strategy_service esté listo:**

```python
# En lifespan, después de strategy_service.start():
strategy_service.start()
await strategy_service.wait_until_ready()

# Luego instanciar IntelligenceEngine
intelligence_engine = IntelligenceEngine(broadcast_callback=broadcast_sync)
app.state.intelligence_engine = intelligence_engine
```

---

## Phase 1: Eliminar Dual Path (crítico)

### Task 1.1: Simplificar App.tsx — eliminar fetch a /ask del PTT

**Files:**
- Modify: `frontend/src/App.tsx:185-281`

**Detail:** El PTT envía la pregunta por WebSocket (a `engine.handle_pilot_question`) Y por HTTP POST a `/ask`. Esto duplica llamadas a CrofAI. La solución es que el PTT **solo** use WebSocket. La respuesta del LLM llega vía `advice_token`/`advice_end` por WebSocket. El HTTP `/ask` se reserva para pruebas con curl.

**Change in `handlePTTEnd` — reemplazar todo el bloque fetch:**

```typescript
const handlePTTEnd = async () => {
  const state = useAppStore.getState();
  if (state.radio.mode !== "LISTENING_PILOT") return;

  console.log("[App] PTT Finalizado — Procesando audio...");
  setRadioMode("THINKING_LLM");

  playRadioClick(false);

  const wavBlob = stopCapture();
  stopSpeechRecognition();
  await new Promise((resolve) => setTimeout(resolve, 200));

  let questionText = transcriptionRef.current.trim();
  if (!questionText) {
    console.warn("[App] No se capturó transcripción de voz.");
    setRadioMode("IDLE");
    setCurrentTokens("");
    return;
  }

  // Añadir mensaje del piloto al historial
  addMessageToHistory("pilot", questionText);

  // Enviar pregunta por WebSocket (el engine la procesa y responde vía advice_token/end)
  sendJson("pilot_question", { question: questionText });

  // Enviar WAV para log/archivo
  if (wavBlob) {
    console.log(`[App] Transmitiendo WAV (${wavBlob.size} bytes)...`);
    sendBinary(wavBlob);
  }

  // El radio mode se mantiene en THINKING_LLM hasta que llegue advice_start
  // via WebSocket, que lo cambiará a SPEAKING_ENGINE
};
```

### Task 1.2: Manejar advice_start/end en useWebSocket.ts

**Files:**
- Modify: `frontend/src/hooks/useWebSocket.ts:168-191`

**Detail:** Actualmente `advice_end` ya añade al historial (línea 188: `addMessageToHistory("engineer", fullText)`). Pero `advice_start` y `advice_token` ya manejan el modo radio. Verificar que el flujo funciona sin el fetch HTTP.

**No hay cambios necesarios** — `useWebSocket.ts` ya maneja `advice_start`, `advice_token`, y `advice_end`. Al eliminar el fetch HTTP de App.tsx, la respuesta solo llegará por WebSocket.

**Verificar:** Asegurarse de que `advice_start` establece `setRadioMode("SPEAKING_ENGINE")` y `advice_end` establece `setRadioMode("IDLE")` y llama `addMessageToHistory("engineer", fullText)`. Esto ya existe en `useWebSocket.ts:168-191`.

### Task 1.3: Añadir endpoint /tts separado

**Files:**
- Create: `backend/src/routers/tts.py`
- Modify: `backend/src/main.py` (registrar router)

**Detail:** Sin el fetch HTTP, el frontend necesita una forma de obtener audio TTS para mostrar la respuesta. La respuesta del LLM llega como texto vía WebSocket, y luego el frontend pide TTS a este endpoint.

**Create `backend/src/routers/tts.py`:**

```python
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger("vantare.tts_router")
router = APIRouter()

class TTSRequest(BaseModel):
    text: str

@router.post("/tts")
async def synthesize_tts(request: Request, body: TTSRequest):
    """Convierte texto a audio WAV usando Piper TTS local."""
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Texto vacío")
    
    tts_service = getattr(request.app.state, "tts_service", None)
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS no disponible")
    
    try:
        audio_bytes = await tts_service.synthesize(body.text)
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "X-Response-Text": body.text.strip()[:500],
                "Content-Length": str(len(audio_bytes)),
            }
        )
    except Exception as e:
        logger.error(f"Error en síntesis TTS: {e}")
        raise HTTPException(status_code=500, detail="Error al sintetizar audio")
```

**Register router in `main.py`:**

```python
from src.routers.tts import router as tts_router
# ...
app.include_router(tts_router)
```

### Task 1.4: Simplificar routers/llm.py

**Files:**
- Modify: `backend/src/routers/llm.py`

**Detail:** El endpoint `/ask` ahora es solo para pruebas/curl. Devolver texto plano en lugar de audio WAV, y sin TTS.

**Change:**

```python
@router.post("/ask")
async def ask_copilot(request: Request, body: AskRequest):
    """Endpoint POST para pruebas. Devuelve texto plano."""
    strategy_service = getattr(request.app.state, "strategy_service", None)
    if not strategy_service:
        raise HTTPException(status_code=503, detail="Estrategia no disponible")

    contexto = strategy_service.get_race_summary()

    formatted_history = []
    if body.chat_history:
        for msg in body.chat_history:
            formatted_history.append({"role": msg.role, "content": msg.content})

    full_response = ""
    async for chunk in llamar_copiloto_stream(
        pregunta=body.question,
        contexto=contexto,
        chat_history=formatted_history
    ):
        full_response += chunk

    if not full_response.strip():
        full_response = "No he podido generar una respuesta en este momento."

    return Response(content=full_response, media_type="text/plain")
```

### Task 1.5: Frontend — reproducir TTS desde WebSocket response

**Files:**
- Modify: `frontend/src/hooks/useWebSocket.ts`

**Detail:** Cuando llega `advice_end`, el frontend tiene el texto completo. Debe pedir el audio TTS al backend y reproducirlo.

**Add after `advice_end` handler in useWebSocket.ts:**

```typescript
case "advice_end": {
  setRadioMode("IDLE");
  const fullText = payload.full_text || "";
  setLatestAdvice(fullText);
  addMessageToHistory("engineer", fullText);
  setCurrentTokens("");

  // Solicitar audio TTS al backend
  if (fullText && !fullText.startsWith("---")) {
    const configState = useAppStore.getState().config;
    const baseUrl = `http://${configState.vllmIP || "localhost"}:${configState.serverPort || 8008}`;
    
    fetch(`${baseUrl}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: fullText }),
    })
    .then(async (res) => {
      if (!res.ok) throw new Error(`TTS returned ${res.status}`);
      const audioBlob = await res.blob();
      const url = URL.createObjectURL(audioBlob);
      const audio = new Audio(url);
      setRadioMode("SPEAKING_ENGINE");
      audio.onended = () => {
        URL.revokeObjectURL(url);
        setRadioMode("IDLE");
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        setRadioMode("IDLE");
      };
      await audio.play();
    })
    .catch((err) => {
      console.warn("[WS] TTS no disponible, mostrando solo texto:", err);
      setRadioMode("IDLE");
    });
  }
  break;
}
```

---

## Phase 2: Robustez del Engine

### Task 2.1: Proteger al piloto de preemption automática

**Files:**
- Modify: `backend/src/intelligence/engine.py:189-203`

**Detail:** Cuando el engine está procesando una `PilotQuestion`, los triggers automáticos no deberían interrumpirla. Solo triggers de prioridad CRITICAL pueden preemptar.

**Change in `evaluate_cycle` — añadir guarda al inicio del loop de triggers:**

```python
# 2. Manejo de la pregunta del piloto (PilotQuestionTrigger manual)
if pilot_question:
    # ... código existente ...
    return

# 3. Iterar sobre los 12 triggers estándar
for trigger in self.triggers:
    # Si el piloto tiene una pregunta activa (ya sea en curso o pendiente),
    # saltar triggers automáticos a menos que sean CRITICAL
    if self._active_trigger_name == "Pregunta directa del piloto" and trigger.priority != Priority.CRITICAL:
        continue
    
    if trigger.should_evaluate() and trigger.condition(telemetry_dict, strategy_dict, session_dict):
        # ... código existente ...
```

### Task 2.2: Cola de reproducción TTS

**Files:**
- Create: `frontend/src/services/audioQueue.ts`
- Modify: `frontend/src/hooks/useWebSocket.ts` (usar cola)

**Detail:** Si dos respuestas llegan seguidas (trigger automático + pregunta), la segunda interrumpe la primera. Una cola FIFO garantiza que los mensajes se reproduzcan en orden sin pisarse.

**Create `frontend/src/services/audioQueue.ts`:**

```typescript
type AudioTask = {
  text: string;
  url: string;
};

class AudioQueue {
  private queue: AudioTask[] = [];
  private playing = false;
  private currentAudio: HTMLAudioElement | null = null;

  enqueue(text: string, url: string): void {
    this.queue.push({ text, url });
    if (!this.playing) {
      this.playNext();
    }
  }

  stop(): void {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio = null;
    }
    this.queue = [];
    this.playing = false;
  }

  private playNext(): void {
    if (this.queue.length === 0) {
      this.playing = false;
      return;
    }

    this.playing = true;
    const task = this.queue.shift()!;
    const audio = new Audio(task.url);
    this.currentAudio = audio;

    audio.onended = () => {
      URL.revokeObjectURL(task.url);
      this.currentAudio = null;
      this.playNext();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(task.url);
      this.currentAudio = null;
      this.playNext();
    };
    audio.play().catch(() => this.playNext());
  }
}

export const audioQueue = new AudioQueue();
```

**Use in useWebSocket.ts (en el advice_end handler):**

```typescript
case "advice_end": {
  // ... manejo de estado ...
  
  // Usar cola de audio en lugar de reproducir directamente
  if (fullText && !fullText.startsWith("---")) {
    const configState = useAppStore.getState().config;
    const baseUrl = `http://${configState.vllmIP || "localhost"}:${configState.serverPort || 8008}`;
    
    fetch(`${baseUrl}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: fullText }),
    })
    .then(async (res) => {
      if (!res.ok) throw new Error(`TTS returned ${res.status}`);
      const audioBlob = await res.blob();
      const url = URL.createObjectURL(audioBlob);
      audioQueue.enqueue(fullText, url);
      setRadioMode("SPEAKING_ENGINE");
    })
    .catch((err) => {
      console.warn("[WS] TTS no disponible:", err);
      setRadioMode("IDLE");
    });
  }
  break;
}
```

**Also call `audioQueue.stop()` in App.tsx handlePTTStart:**

```typescript
// Al inicio de handlePTTStart, interrumpir cualquier TTS en curso
import { audioQueue } from "./services/audioQueue";

const handlePTTStart = () => {
  audioQueue.stop();
  // ... resto ...
};
```

### Task 2.3: Protección time jump en triggers

**Files:**
- Modify: `backend/src/intelligence/triggers.py:43-48`

**Detail:** Si Windows hiberna/suspende, `time.monotonic()` salta hacia adelante. Todos los triggers expiran a la vez y se disparan simultáneamente.

**Change in `BaseTrigger.should_evaluate`:**

```python
def should_evaluate(self, current_time: Optional[float] = None) -> bool:
    """Controla el cooldown con detección de time jumps."""
    now = current_time if current_time is not None else time.monotonic()
    elapsed = now - self.last_triggered
    
    # Detectar time jump (suspensión/hibernación)
    if elapsed > self.min_interval * 3 and self.last_triggered > 0:
        logger.debug(f"Time jump detectado en trigger '{self.description}': {elapsed:.0f}s")
        self.last_triggered = now
        return False
    
    return elapsed >= self.min_interval
```

Añadir `logger = logging.getLogger(__name__)` al inicio del archivo.

---

## Phase 3: Mejoras de Infraestructura

### Task 3.1: Unificar los dos clientes LLM

**Files:**
- Modify: `backend/src/services/llm_service.py` (eliminar duplicación)
- Modify: `backend/src/intelligence/llm_client.py` (unificar)

**Detail:** Existen DOS implementaciones de cliente LLM:
- `llm_service.py` → `llamar_copiloto_stream()` (httpx directo, usado por /ask)
- `llm_client.py` → `VLLMClient.ask_streaming()` (OpenAI SDK, usado por engine)

Solución: `llamar_copiloto_stream()` en `llm_service.py` debe usar `VLLMClient` internamente.

**Change in `llm_service.py`:**

```python
# Eliminar la implementación directa con httpx
# y delegar en VLLMClient

from src.intelligence.llm_client import VLLMClient

_client_instance = None

def _get_client() -> VLLMClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = VLLMClient()
    return _client_instance

async def llamar_copiloto_stream(pregunta: str, contexto: dict, chat_history: list = None):
    """Delega en VLLMClient para mantener un único punto de integración con CrofAI."""
    client = _get_client()
    
    # El VLLMClient.ask_streaming emite AdviceStart/Token/End via broadcaster
    # Nosotros necesitamos los tokens en crudo para /ask
    prompt = f"PREGUNTA DEL PILOTO: {pregunta}\n\nCONTEXTO: {json.dumps(contexto, ensure_ascii=False)}"
    
    # ... integrar con prompt_templates ...
```

### Task 3.2: Cache con TTL en lmu_api.py

**Files:**
- Modify: `backend/src/services/lmu_api.py`

**Detail:** Los 3 caches globales (`_weather_cache`, `_strategy_usage_cache`, `_garage_wear_cache`) crecen sin límite. Añadir `time.monotonic()` para saber cuándo fue la última actualización y podar.

```python
# Añadir timestamps de última actualización
_last_update: dict = {"weather": 0.0, "strategy_usage": 0.0, "garage_wear": 0.0}

def get_cache_sizes() -> dict[str, int]:
    """Incluir edad del cache para diagnóstico."""
    with _cache_lock:
        now = time.monotonic()
        ages = {k: f"{(now - v):.0f}s" for k, v in _last_update.items()}
        return {
            "weather": len(_weather_cache),
            "weather_age": ages.get("weather", "N/A"),
            "strategy_usage": len(_strategy_usage_cache),
            "strategy_usage_age": ages.get("strategy_usage", "N/A"),
            "garage_wear": len(_garage_wear_cache),
            "garage_wear_age": ages.get("garage_wear", "N/A"),
        }
```

Actualizar `_last_update` en cada swap atómico en `poll_api()`.

### Task 3.3: Logging con advice_id

**Files:**
- Modify: `backend/src/intelligence/engine.py` (añadir logs con advice_id)
- Modify: `backend/src/intelligence/llm_client.py` (añadir logs con advice_id)
- Modify: `backend/src/routers/websocket.py` (añadir log cuando se recibe pilot_question)

**Detail:** Cada pregunta del piloto tiene un `advice_id`. Añadirlo a todos los logs relevantes para poder trazar el flujo.

**In websocket.py (pilot_question handler):**

```python
if event == "pilot_question":
    question = msg.get("data", {}).get("question", "")
    if question:
        import uuid
        advice_id = str(uuid.uuid4())
        logger.info(f"[WS] pilot_question recibida: advice_id={advice_id} texto=\"{question[:60]}...\"")
        # Pasar advice_id al engine
        engine = getattr(app_state, "intelligence_engine", None)
        if engine:
            asyncio.create_task(engine.handle_pilot_question(question, advice_id=advice_id))
```

**In engine.py — añadir parámetro advice_id a handle_pilot_question y pasarlo a evaluate_cycle y _run_llm_stream.**

**In llm_client.py — añadir advice_id a todos los logger.info/warning:**

```python
logger.info(f"[{advice_id}] CrofAI streaming iniciado: model={self._model}, max_tokens={max_tokens}")
logger.info(f"[{advice_id}] CrofAI streaming completado: {len(full_text)} chars, tokens generados")
```

---

## Phase 4: State Recovery (futuro)

### Task 4.1: WebSocket reconnect con state recovery (post-MVP)

**Detail:** Cuando el WebSocket se reconecta, debería:
1. Solicitar el estado actual del engine al backend
2. Recuperar el historial de mensajes recientes
3. Re-sincronizar el modo radio

**Backend:** Añadir mensaje `sync_request` que el frontend envía al reconectar:
```python
if event == "sync_request":
    # Devolver estado actual del engine
    response = {
        "event": "sync_state",
        "data": {
            "mode": radio_mode,
            "message_history": last_n_messages(10),
            "telemetry": latest_telemetry,
        }
    }
```

**Frontend:** En `useWebSocket.ts` onopen, enviar `sync_request`.

---

## Dependency Graph

```
Phase 0 ──> Phase 1 ──> Phase 2 ──> Phase 3
  │                      │
  ├── 0.1 timeout fetch  │
  ├── 0.2 timeout LLM    │
  ├── 0.3 selectores     │
  ├── 0.4 validación     │
  ├── 0.5 pausar engine   │
  └── 0.6 barrera        │
                         │
              ┌──────────┘
              │
     Phase 1 depende de Phase 0 (timeouts)
     Phase 2 depende de Phase 1 (Dual Path eliminado)
     Phase 3 independiente (puede ejecutarse en cualquier orden)
```

**Orden de implementación recomendado:**

1. Phase 0 Tasks (cualquier orden, son independientes)
2. Phase 1 Tasks (1.1 → 1.2 → 1.3 → 1.4 → 1.5)
3. Phase 2 Tasks (2.1 → 2.2 → 2.3)
4. Phase 3 Tasks (cualquier orden)

---

## Criterios de Aceptación

- [ ] PTT envía pregunta SOLO por WebSocket (nunca dos veces)
- [ ] La respuesta del LLM llega vía `advice_token`/`advice_end` por WebSocket
- [ ] El historial muestra mensajes sin duplicados
- [ ] Fetch timeout a los 15s muestra error limpio (no UI congelada)
- [ ] VLLMClient timeout a los 25s libera la tarea del engine
- [ ] Dashboard no se re-renderiza a 20Hz cuando solo cambia telemetría
- [ ] Configuración rechaza IP/puerto/hotkey inválidos con mensaje visible
- [ ] Engine no ejecuta triggers si no hay WebSocket conectado
- [ ] Piloto no es interrumpido por triggers automáticos (solo CRITICAL)
- [ ] TTS en cola: dos respuestas seguidas no se pisan
- [ ] Time jumps (hibernación) no causan avalancha de triggers
- [ ] El backend arranca solo cuando StrategyService tiene datos
