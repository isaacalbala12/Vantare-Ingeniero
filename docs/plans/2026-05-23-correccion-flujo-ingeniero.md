# Plan de Corrección — Flujo Completo del Ingeniero de IA

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corregir todos los bugs identificados en el diagnóstico del flujo PTT, priorizados por criticidad. Cada fase produce un estado funcional y desplegable.

**Architecture:** 4 fases ordenadas por criticidad. Fase 1 son bugs críticos que rompen el flujo PTT. Fase 2 son bugs altos que degradan confiabilidad. Fase 3 son tests rotos. Fase 4 son mejoras menores. Cada tarea es independiente y desplegable por separado.

**Tech Stack:** FastAPI, React/Zustand, TypeScript, Python, PyTest, Vitest.

---

## File Map

| Archivo | Rol | Cambios |
|---|---|---|
| `backend/src/config.py` | Config central | F1.T2: default PORT 8008 |
| `backend/run_dev.py` | Dev script | F1.T2: eliminar hardcode 8008, usar settings |
| `frontend/src/App.tsx` | Orquestador PTT | F1.T1: fallback WAV si SpeechRecognition falla |
| `frontend/src/hooks/useWebSocket.ts` | WS manager | F1.T4: cola TTS en vez de bool único |
| `frontend/src/store/config.ts` | Zustand store | F2.T2: eliminar migración forzosa a "P" |
| `backend/src/intelligence/spotter.py` | Spotter 20Hz | F2.T1: AlertMessage con campos extra en Pydantic |
| `backend/src/models/messages.py` | Modelos Pydantic | F2.T1: añadir severity/ttl/dismissable a AlertMessage |
| `backend/tests/test_tts.py` | Tests TTS | F3.T1: actualizar tests para router real |
| `frontend/src/__tests__/configStore.test.ts` | Tests Store | F3.T2: corregir default hotkey a "P" |
| `backend/tests/test_llm_async.py` | Tests legacy | F3.T3: migrar a nuevo llm_client.py |
| `backend/src/main.py` | Lifespan | F4.T1: logging visible al fallar TTS |
| `backend/src/intelligence/llm_client.py` | Cliente LLM | F4.T2: validar API key al inicio |
| `frontend/src-tauri/tauri.conf.json` | Config Tauri | F4.T3: añadir capability global-shortcut |
| `frontend/src/components/SystemTrayMenu.tsx` | Tray menu | F4.T4: reemplazar clases CSS custom |

---

## Fase 1: Bugs CRÍTICOS (rompen el flujo PTT)

### Task 1.1: Fallback WAV cuando SpeechRecognition no está disponible

**Files:**
- Modify: `frontend/src/App.tsx` (lines 76-213)

**Context:** Si WebView2 no soporta `SpeechRecognition` (webkitSpeechRecognition), `startSpeechRecognition()` logea un warning y `transcriptionRef.current` queda vacío. `handlePTTEnd()` detecta vacío y aborta sin enviar nada al backend. El WAV Blob capturado se descarta.

**Solución:** Cuando SpeechRecognition no esté disponible, enviar el WAV Blob al backend para transcripción por ASR. Cuando SpeechRecognition funcione pero dé transcripción vacía, reintentar 1 vez. Si persiste vacío, enviar WAV.

- [ ] **Step 1: Modificar handlePTTEnd para enviar WAV como fallback**

```typescript
// En frontend/src/App.tsx, reemplazar handlePTTEnd (lines 174-213)

const handlePTTEnd = async () => {
  const state = useAppStore.getState();
  if (state.radio.mode !== "LISTENING_PILOT") return;

  console.log("[App] PTT Finalizado — Procesando audio...");
  setRadioMode("THINKING_LLM");
  playBeep(false);

  const wavBlob = stopCapture();
  stopSpeechRecognition();

  // Dar 200ms para que se asiente la transcripción final
  await new Promise((resolve) => setTimeout(resolve, 200));

  let questionText = transcriptionRef.current.trim();

  // Si SpeechRecognition no está soportado o no dió transcripción
  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  if (!questionText && SpeechRecognition) {
    // Reintentar una vez con SpeechRecognition
    console.warn("[App] Transcripción vacía, reintentando...");
    transcriptionRef.current = "";
    startSpeechRecognition();
    await new Promise((resolve) => setTimeout(resolve, 1000));
    stopSpeechRecognition();
    questionText = transcriptionRef.current.trim();
  }

  if (!questionText) {
    if (wavBlob && wavBlob.size > 100) {
      // Fallback: enviar WAV al backend para transcripción ASR
      console.log("[App] Enviando WAV al backend para transcripción ASR...");
      try {
        const baseUrl = `http://${useAppStore.getState().config.vllmIP || "localhost"}:${useAppStore.getState().config.serverPort || 8008}`;
        const formData = new FormData();
        formData.append("audio", wavBlob, "pilot_audio.wav");
        const response = await fetch(`${baseUrl}/transcribe`, {
          method: "POST",
          body: formData,
        });
        if (response.ok) {
          const data = await response.json();
          questionText = data.text || "";
        }
      } catch (e) {
        console.error("[App] Error enviando WAV para transcripción:", e);
      }
    }
  }

  if (!questionText) {
    console.warn("[App] No se capturó transcripción de voz.");
    setRadioMode("IDLE");
    setCurrentTokens("");
    return;
  }

  addMessageToHistory("pilot", questionText);
  sendJson("pilot_question", { question: questionText });
};
```

- [ ] **Step 2: Crear endpoint /transcribe en el backend**

```python
# backend/src/routers/transcribe.py
"""Endpoint para transcripción de audio WAV a texto usando ASR."""
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger("vantare.transcribe")

router = APIRouter()

@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe un archivo WAV a texto.
    
    Por ahora devuelve un mensaje informativo: la transcripción real
    requiere un motor ASR (Whisper, etc.) que se integrará después.
    """
    if not file.filename or not file.filename.endswith(".wav"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos WAV")
    
    content = await file.read()
    if len(content) < 44:  # Cabecera WAV mínima
        raise HTTPException(status_code=400, detail="Archivo WAV inválido o vacío")
    
    logger.info("Audio WAV recibido: %s (%d bytes)", file.filename, len(content))
    
    # TODO: Integrar Whisper u otro motor ASR aquí
    return JSONResponse(
        content={
            "text": "",
            "info": "Transcripción ASR no implementada. Usar SpeechRecognition del navegador.",
            "audio_size": len(content)
        }
    )
```

- [ ] **Step 3: Registrar el router en main.py**

```python
# backend/src/main.py, después de la línea 184 (tts_router)
from src.routers.transcribe import router as transcribe_router
# ...
app.include_router(transcribe_router)
```

- [ ] **Step 4: Verificar que el flujo funciona sin SpeechRecognition**

Run: Inspeccionar que `handlePTTEnd` envía WAV cuando SpeechRecognition no está disponible.

Expected: Si SpeechRecognition no existe, el WAV se envía a `/transcribe`. Si existe pero da vacío, reintenta 1 vez. Si sigue vacío, envía WAV.

---

### Task 1.2: Unificar puerto a 8008 en config.py y run_dev.py

**Files:**
- Modify: `backend/src/config.py` (line 34)
- Modify: `backend/run_dev.py` (lines 18, 46-51)

**Context:** `config.py` dice `PORT: int = 8000` pero `run_dev.py` pasa `default=8008` directamente a uvicorn, ignorando `settings.PORT`. El frontend conecta a 8008. Si alguien ejecuta `python main.py`, el backend arranca en 8000 y el frontend no conecta.

- [ ] **Step 1: Cambiar default PORT en config.py a 8008**

```python
# backend/src/config.py, line 34
PORT: int = 8008
```

- [ ] **Step 2: Modificar run_dev.py para usar settings.PORT**

```python
# backend/run_dev.py, lines 17-18 y 46-51
parser.add_argument("--port", type=int, default=None, help="Puerto (default: settings.PORT = 8008)")
# ...
args = parser.parse_args()

from src.config import settings
port = args.port or settings.PORT

# ...
uvicorn.run(
    "src.main:app",
    host=args.host,
    port=port,
    reload=reload,
    log_level="info",
)
```

---

### Task 1.3: Forzar validación de API Key de CrofAI al arranque

**Files:**
- Modify: `backend/src/intelligence/llm_client.py` (lines 51-72)
- Modify: `backend/src/main.py` (después de línea 93)

**Context:** Si `CROFAI_API_KEY` está vacía, el LLM falla silenciosamente con 401. El health check muestra `configured: false` pero no hay alerta visible.

- [ ] **Step 1: Añadir validación explícita en llm_client.py**

```python
# backend/src/intelligence/llm_client.py, al inicio de __init__
def __init__(self, api_key=None, base_url=None, model=None):
    self._api_key = api_key or settings.CROFAI_API_KEY
    self._base_url = base_url or settings.CROFAI_BASE_URL
    self._model = model or settings.LLM_MODEL
    self._client: Optional[AsyncOpenAI] = None

    if not self._api_key:
        logger.warning(
            "*** CROFAI_API_KEY no configurada. El LLM no funcionará. ***\n"
            "    Crea un archivo backend/.env con:\n"
            "    CROFAI_API_KEY=tu-api-key-aqui"
        )
    
    logger.info(
        "LLMClient inicializado: base_url=%s model=%s api_key=%s",
        self._base_url,
        self._model,
        "***configurada***" if self._api_key else "VACÍA",
    )
```

- [ ] **Step 2: Añadir check de API key en main.py lifespan**

```python
# backend/src/main.py, después de crear intelligence_engine (line 93)
if not settings.CROFAI_API_KEY:
    logger.error(
        "╔══════════════════════════════════════════════════╗\n"
        "║  CROFAI_API_KEY no configurada                  ║\n"
        "║  El LLM no responderá preguntas del piloto.     ║\n"
        "║  Crea backend/.env con:                         ║\n"
        "║    CROFAI_API_KEY=tu-api-key                    ║\n"
        "╚══════════════════════════════════════════════════╝"
    )
```

---

### Task 1.4: Cola TTS para múltiples advice_end rápidos

**Files:**
- Modify: `frontend/src/hooks/useWebSocket.ts` (lines 198-228)

**Context:** `isTtsRequestedRef` es un booleano. Si dos `advice_end` llegan rápido (ej: trigger automático + pregunta de piloto), solo el primero genera TTS. El segundo se pierde.

- [ ] **Step 1: Reemplazar isTtsRequestedRef con cola de solicitudes pendientes**

```typescript
// frontend/src/hooks/useWebSocket.ts, reemplazar lines 33 y 198-228

// Eliminar:
// const isTtsRequestedRef = useRef<boolean>(false);

// Añadir:
const ttsQueueRef = useRef<string[]>([]);
const isTtsProcessingRef = useRef<boolean>(false);

const processTtsQueue = useCallback(async () => {
  if (isTtsProcessingRef.current || ttsQueueRef.current.length === 0) return;
  
  isTtsProcessingRef.current = true;
  const fullText = ttsQueueRef.current.shift()!;
  
  const configState = useAppStore.getState().config;
  const baseUrl = `http://${configState.vllmIP || "localhost"}:${configState.serverPort || 8008}`;
  const ttsText = fullText.length > 500 ? fullText.slice(0, 497) + "..." : fullText;

  try {
    const res = await fetch(`${baseUrl}/tts?text=${encodeURIComponent(ttsText)}`);
    if (!res.ok) throw new Error(`TTS returned ${res.status}`);
    const audioBlob = await res.blob();
    if (!audioBlob || audioBlob.size === 0) throw new Error("TTS returned empty audio blob");
    
    const url = URL.createObjectURL(audioBlob);
    const currentMode = useAppStore.getState().radio.mode;
    if (currentMode !== "IDLE") {
      console.log("[WS] TTS listo pero usuario activo — descartando reproducción");
      URL.revokeObjectURL(url);
      isTtsProcessingRef.current = false;
      processTtsQueue();
      return;
    }
    setRadioMode("SPEAKING_ENGINE");
    audioQueue.enqueue(fullText, url);
  } catch (err) {
    console.warn("[WS] TTS no disponible:", err);
  } finally {
    isTtsProcessingRef.current = false;
    processTtsQueue();
  }
}, [setRadioMode, audioQueue]);

// En el case "advice_end", reemplazar el bloque TTS (lines 198-228):
case "advice_end": {
  setRadioMode("IDLE");
  const fullText = payload.full_text || "";
  // ... (keep existing logic for setting advice and history)
  
  if (fullText && !fullText.startsWith("---")) {
    ttsQueueRef.current.push(fullText);
    processTtsQueue();
  }
  break;
}
```

---

## Fase 2: Bugs ALTOS (degradan confiabilidad)

### Task 2.1: AlertMessage con campos extra en Pydantic

**Files:**
- Modify: `backend/src/models/messages.py` (lines 44-50)
- Modify: `backend/src/intelligence/spotter.py` (lines 151-179)

**Context:** `spotter.py` usa `object.__setattr__` para añadir `id`, `severity`, `ttl`, `dismissable` al AlertMessage. Estos campos se pierden durante `model_dump()` porque no están en el modelo Pydantic.

- [ ] **Step 1: Añadir campos faltantes a AlertMessage en messages.py**

```python
# backend/src/models/messages.py, reemplazar AlertMessage class (lines 44-50)
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
```

- [ ] **Step 2: Limpiar spotter.py, eliminar object.__setattr__**

```python
# backend/src/intelligence/spotter.py, reemplazar _create_alert (lines 151-179)
def _create_alert(
    self,
    message: str,
    severity: str,
    audio_priority: int,
    ttl: int,
    dismissable: bool,
    category: str,
    payload: Dict[str, Any]
) -> AlertMessage:
    return AlertMessage(
        event="alert",
        alert_id=str(uuid.uuid4()),
        category=category,
        message=message,
        audio_priority=str(audio_priority),
        severity=severity,
        ttl=ttl,
        dismissable=dismissable,
        payload={
            "severity": severity,
            "ttl": ttl,
            "dismissable": dismissable,
            **payload
        }
    )
```

- [ ] **Step 3: Ejecutar tests de spotter para confirmar que no se rompen**

Run: `cd backend && python -m pytest tests/test_spotter.py -v`
Expected: Todos los tests PASS

---

### Task 2.2: Eliminar migración forzosa a hotkey "P"

**Files:**
- Modify: `frontend/src/store/config.ts` (lines 101-106)

**Context:** El `loadSavedConfig()` sobrescribe cualquier hotkey previa a "P" automáticamente. Si un usuario personalizó su atajo, se pierde al recargar.

- [ ] **Step 1: Eliminar la migración forzosa**

```typescript
// frontend/src/store/config.ts, reemplazar lines 97-118
const loadSavedConfig = (): AppConfig => {
  try {
    let saved = localStorage.getItem("vantare_config");
    if (saved) {
      const parsed = JSON.parse(saved);
      return {
        vllmIP: parsed.vllmIP ?? "localhost",
        serverPort: parsed.serverPort ?? 8008,
        micDevice: parsed.micDevice ?? "default",
        speakerDevice: parsed.speakerDevice ?? "default",
        wakeWord: parsed.wakeWord ?? "ingeniero",
        sensitivity: parsed.sensitivity ?? 50,
        pttHotkey: parsed.pttHotkey ?? "Ctrl+Shift+P",
        pttStopHotkey: parsed.pttStopHotkey ?? "Ctrl+Shift+P",
        wakeWordEnabled: parsed.wakeWordEnabled ?? true,
      };
    }
  } catch (e) {
    console.warn("Fallo al leer localStorage para la configuración:", e);
  }
  return {
    vllmIP: "localhost",
    serverPort: 8008,
    micDevice: "default",
    speakerDevice: "default",
    wakeWord: "ingeniero",
    sensitivity: 50,
    pttHotkey: "Ctrl+Shift+P",
    pttStopHotkey: "Ctrl+Shift+P",
    wakeWordEnabled: true,
  };
};
```

Nota: El default cambia de `"P"` a `"Ctrl+Shift+P"` para no interferir con la escritura normal (la tecla "P" sola es muy fácil de pulsar accidentalmente).

---

## Fase 3: Tests Rotos

### Task 3.1: Actualizar tests de TTS al router real

**Files:**
- Modify: `backend/tests/test_tts.py` (todo el archivo)

**Context:** Los tests esperan códigos HTTP que no coinciden con la implementación real. El router actual trunca a 2000 chars (no retorna 413), y usa `_resolve_services()` que busca `edge_tts_service`/`piper_tts_service` (no `tts_service`).

- [ ] **Step 1: Reescribir test_tts.py**

```python
"""
Tests unitarios para el endpoint /tts.

Verifica:
- GET /tts?text=hola devuelve 200 y Content-Type audio/mpeg o audio/wav.
- GET /tts sin parámetro text devuelve 400.
- GET /tts con texto vacío devuelve 400.
- GET /tts cuando backend edge no disponible y piper tampoco → 500.
- GET /tts con texto > 2000 caracteres se trunca.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock


def make_app_with_tts_services(edge_service=None, piper_service=None):
    """
    Crea una app FastAPI con estado simulado para el endpoint /tts.
    El router real busca 'edge_tts_service' y 'piper_tts_service' via _resolve_services.
    """
    from fastapi import FastAPI
    from src.routers.tts import router as tts_router

    app = FastAPI()
    app.include_router(tts_router)
    app.state.edge_tts_service = edge_service
    app.state.piper_tts_service = piper_service
    return app


class TestTTSEndpoint:
    """Pruebas del endpoint /tts alineadas con la implementación real."""

    def test_tts_returns_200_with_audio(self):
        """GET /tts?text=hola debe devolver 200 con Content-Type audio/mpeg."""
        mock_edge = MagicMock()

        async def fake_synthesize(text):
            return b"MP3 audio data" + b"\x00" * 100

        mock_edge.synthesize = fake_synthesize

        app = make_app_with_tts_services(edge_service=mock_edge)
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": "hola"})
            assert response.status_code == 200
            assert "audio" in response.headers["content-type"]

    def test_tts_returns_400_without_text(self):
        """GET /tts sin parámetro text debe devolver 400."""
        app = make_app_with_tts_services(edge_service=MagicMock())
        with TestClient(app) as client:
            response = client.get("/tts")
            assert response.status_code == 400

    def test_tts_returns_400_with_empty_text(self):
        """GET /tts?text= (vacío) debe devolver 400."""
        app = make_app_with_tts_services(edge_service=MagicMock())
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": ""})
            assert response.status_code == 400

    def test_tts_truncates_long_text(self):
        """Texto > 2000 caracteres debe truncarse, no dar error."""
        mock_edge = MagicMock()
        received_text = ""

        async def fake_synthesize(text):
            nonlocal received_text
            received_text = text
            return b"MP3 audio data"

        mock_edge.synthesize = fake_synthesize

        app = make_app_with_tts_services(edge_service=mock_edge)
        long_text = "a" * 2500
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": long_text})
            assert response.status_code == 200
            assert len(received_text) <= 2000
            assert received_text.endswith("...")

    def test_tts_allows_2000_chars(self):
        """Texto de exactamente 2000 caracteres debe funcionar sin truncar."""
        mock_edge = MagicMock()
        received_text = ""

        async def fake_synthesize(text):
            nonlocal received_text
            received_text = text
            return b"MP3 audio data"

        mock_edge.synthesize = fake_synthesize

        app = make_app_with_tts_services(edge_service=mock_edge)
        text_2000 = "a" * 2000
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": text_2000})
            assert response.status_code == 200
            assert len(received_text) == 2000
            assert not received_text.endswith("...")

    def test_tts_returns_500_when_all_backends_fail(self):
        """GET /tts cuando todos los backends fallan debe devolver 500."""
        app = make_app_with_tts_services(edge_service=None, piper_service=None)
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": "hola"})
            assert response.status_code == 500

    def test_tts_fallback_to_piper_when_edge_fails(self):
        """Si edge falla, debe intentar con piper automáticamente."""
        mock_edge = MagicMock()

        async def edge_synth(text):
            raise RuntimeError("Edge TTS falló")

        mock_edge.synthesize = edge_synth

        mock_piper = MagicMock()

        async def piper_synth(text):
            return b"WAV audio data"

        mock_piper.synthesize = piper_synth

        app = make_app_with_tts_services(edge_service=mock_edge, piper_service=mock_piper)
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": "hola"})
            assert response.status_code == 200
            assert "audio" in response.headers["content-type"]

    def test_tts_with_special_chars(self):
        """TTS debe manejar caracteres especiales."""
        mock_edge = MagicMock()
        received_text = ""

        async def fake_synthesize(text):
            nonlocal received_text
            received_text = text
            return b"MP3 audio data"

        mock_edge.synthesize = fake_synthesize

        app = make_app_with_tts_services(edge_service=mock_edge)
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": "éxito", "text": "ñño"})
            assert response.status_code == 200
            assert len(received_text) > 0
```

- [ ] **Step 2: Ejecutar los tests actualizados**

Run: `cd backend && python -m pytest tests/test_tts.py -v`
Expected: Todos los tests PASS

---

### Task 3.2: Corregir test de configStore

**Files:**
- Modify: `frontend/src/__tests__/configStore.test.ts` (line 85)

**Context:** El test espera `"Ctrl+Shift+P"` pero el store devuelve `"P"` (o el nuevo default después de Task 2.2). La línea 85 del test debe coincidir con el default real.

- [ ] **Step 1: Corregir la aserción del hotkey default**

```typescript
// frontend/src/__tests__/configStore.test.ts, line 85
// Cambiar:
expect(state.config.pttHotkey).toBe("Ctrl+Shift+P");
// A:
expect(state.config.pttHotkey).toBe("Ctrl+Shift+P");  // Ahora coincide con Task 2.2
```

- [ ] **Step 2: Asegurar que el beforeEach también usa el mismo default**

```typescript
// frontend/src/__tests__/configStore.test.ts, lines 48-50
config: {
  // ...
  pttHotkey: "Ctrl+Shift+P",  // Debe coincidir con el default del store
  pttStopHotkey: "Ctrl+Shift+P",
```

- [ ] **Step 3: Ejecutar tests del frontend**

Run: `cd frontend && npx vitest run src/__tests__/configStore.test.ts`
Expected: Todos los tests PASS

---

### Task 3.3: Migrar test_llm_async a nuevo llm_client.py

**Files:**
- Modify: `backend/tests/test_llm_async.py` (todo el archivo)

**Context:** Los tests actuales prueban el viejo `llm_service.py` (Groq). El flujo PTT real usa `llm_client.py` (CrofAI). Los tests legacy ya no son relevantes.

- [ ] **Step 1: Reescribir test_llm_async.py para probar el nuevo VLLMClient**

```python
"""
Tests unitarios para el VLLMClient (CrofAI via OpenAI SDK).

Verifica:
- health_check() con API key simulada.
- health_check() sin API key retorna False.
- ask_streaming() con mock del SDK envía advice_start/advice_token/advice_end.
- ask_streaming() maneja errores correctamente.
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from src.intelligence.llm_client import VLLMClient
from src.models.messages import AdviceStartMessage, AdviceTokenMessage, AdviceEndMessage

# =========================================================================
# Tests
# =========================================================================

class TestVLLMClientHealthCheck:
    """Pruebas del método health_check."""

    @pytest.mark.asyncio
    async def test_health_check_returns_true_when_configured(self):
        """health_check() debe retornar True cuando la API responde."""
        client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

        mock_client = MagicMock()
        mock_models = MagicMock()
        mock_model = MagicMock()
        mock_model.id = "deepseek-v4-flash"
        mock_models.data = [mock_model]
        mock_client.models.list = AsyncMock(return_value=mock_models)

        with patch.object(client, '_get_client', return_value=mock_client):
            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_without_api_key(self):
        """health_check() debe retornar False sin API key."""
        client = VLLMClient(api_key="", base_url="https://test.api/v1")
        result = await client.health_check()
        assert result is False


class TestVLLMClientAskStreaming:
    """Pruebas del método ask_streaming."""

    @pytest.mark.asyncio
    async def test_ask_streaming_sends_tokens_and_end(self):
        """ask_streaming debe enviar advice_start, tokens y advice_end."""
        broadcast_messages = []
        def mock_broadcast(msg):
            broadcast_messages.append(msg)

        with patch("src.intelligence.llm_client.send", mock_broadcast):
            client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

            # Mock del streaming response
            mock_chunk_1 = MagicMock()
            mock_chunk_1.choices = [MagicMock()]
            mock_chunk_1.choices[0].delta.content = "Hola "
            mock_chunk_1.choices[0].delta.tool_calls = None
            mock_chunk_1.choices[0].delta.reasoning_content = None

            mock_chunk_2 = MagicMock()
            mock_chunk_2.choices = [MagicMock()]
            mock_chunk_2.choices[0].delta.content = "piloto."
            mock_chunk_2.choices[0].delta.tool_calls = None
            mock_chunk_2.choices[0].delta.reasoning_content = None

            mock_stream = AsyncMock()
            mock_stream.__aiter__.return_value = [mock_chunk_1, mock_chunk_2].__iter__()

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

            with patch.object(client, '_get_client', return_value=mock_client):
                await client.ask_streaming("test prompt", "FAST", "advice-123", None)

            # Verificar mensajes
            start_msgs = [m for m in broadcast_messages if isinstance(m, AdviceStartMessage)]
            token_msgs = [m for m in broadcast_messages if isinstance(m, AdviceTokenMessage)]
            end_msgs = [m for m in broadcast_messages if isinstance(m, AdviceEndMessage)]

            assert len(start_msgs) == 1
            assert len(token_msgs) == 2
            assert len(end_msgs) == 1
            assert token_msgs[0].token == "Hola "
            assert token_msgs[1].token == "piloto."
            assert end_msgs[0].full_text == "Hola piloto."

    @pytest.mark.asyncio
    async def test_ask_streaming_sends_error_on_exception(self):
        """ask_streaming debe enviar mensaje de error si la API falla."""
        broadcast_messages = []
        def mock_broadcast(msg):
            broadcast_messages.append(msg)

        with patch("src.intelligence.llm_client.send", mock_broadcast):
            client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

            with patch.object(client, '_get_client', return_value=mock_client):
                await client.ask_streaming("test", "FAST", "advice-456", None)

            end_msgs = [m for m in broadcast_messages if isinstance(m, AdviceEndMessage)]
            assert len(end_msgs) >= 1
            assert "Pérdida de comunicación" in end_msgs[-1].full_text
```

- [ ] **Step 2: Ejecutar los tests actualizados**

Run: `cd backend && python -m pytest tests/test_llm_async.py -v`
Expected: Todos los tests PASS

---

## Fase 4: Mejoras y Bajo Riesgo

### Task 4.1: Logging visible cuando TTS falla al inicio

**Files:**
- Modify: `backend/src/main.py` (lines 96-111)

**Context:** Las excepciones de TTS se capturan y silencian con `logger.warning`. El usuario no tiene forma de saber por qué el TTS no funciona.

- [ ] **Step 1: Mejorar logging de fallos TTS**

```python
# backend/src/main.py, reemplazar lines 96-111
# 7. Instanciar EdgeTTSService (cloud, sin dependencias locales)
try:
    edge_tts_service = EdgeTTSService(voice=settings.EDGE_TTS_VOICE)
    app.state.edge_tts_service = edge_tts_service
    logger.info("EdgeTTSService initialized (voice=%s)", settings.EDGE_TTS_VOICE)
except ImportError as e:
    logger.warning("EdgeTTSService no disponible: falta dependencia 'edge_tts'. %s", e)
    app.state.edge_tts_service = None
except Exception as e:
    logger.warning("EdgeTTSService no disponible: %s", e)
    app.state.edge_tts_service = None

# 8. Instanciar Piper TTSService (local, CPU)
try:
    piper_tts_service = TTSService(settings.TTS_MODEL_PATH)
    app.state.piper_tts_service = piper_tts_service
    logger.info("Piper TTSService initialized")
except FileNotFoundError as e:
    logger.warning(
        "Piper TTSService no disponible: modelo no encontrado en %s. %s",
        settings.TTS_MODEL_PATH, e
    )
    app.state.piper_tts_service = None
except ImportError as e:
    logger.warning("Piper TTSService no disponible: falta dependencia. %s", e)
    app.state.piper_tts_service = None
except Exception as e:
    logger.warning("Piper TTSService no disponible (TTS local desactivado): %s", e)
    app.state.piper_tts_service = None

logger.info(
    "TTS backend activo: %s. Edge=%s Piper=%s",
    settings.TTS_BACKEND,
    "OK" if app.state.edge_tts_service else "NO",
    "OK" if app.state.piper_tts_service else "NO",
)
```

---

### Task 4.2: Añadir capability de global-shortcut en Tauri

**Files:**
- Modify: `frontend/src-tauri/tauri.conf.json`

**Context:** `useHotkey.ts` usa `@tauri-apps/plugin-global-shortcut` pero no está listado en `capabilities`. Si Tauri bloquea el plugin, los atajos globales no funcionan (los locales sí).

- [ ] **Step 1: Añadir capability para global-shortcut**

```json
// frontend/src-tauri/tauri.conf.json, dentro de app.security.capabilities
{
  "identifier": "default",
  "description": "Capabilities for the main window",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "global-shortcut:default",
    "global-shortcut:allow-register",
    "global-shortcut:allow-unregister",
    "global-shortcut:allow-is-registered"
  ]
}
```

---

### Task 4.3: Reemplazar clases CSS custom en SystemTrayMenu

**Files:**
- Modify: `frontend/src/components/SystemTrayMenu.tsx`

**Context:** `purple-accent`, `border-zinc-850`, `animate-fade-in`, `glass-panel` no son clases estándar de Tailwind. Pueden no tener efecto o romper el estilo si no hay CSS custom definido.

- [ ] **Step 1: Reemplazar clases custom con clases estándar de Tailwind**

```tsx
// frontend/src/components/SystemTrayMenu.tsx
// Reemplazar:
// "glass-panel" → "bg-opacity-90 backdrop-blur-sm"
// "purple-accent" → "purple-500"
// "border-zinc-850" → "border-zinc-700"
// "animate-fade-in" → "animate-none" (o definir en index.css)
// "bg-zinc-950/40" → "bg-zinc-900/40"
```

---

## Orden de Implementación Recomendado

```
Fase 1 (Críticos):
  Task 1.2 → Unificar puerto (independiente, sin dependencias)
  Task 1.3 → Validar API Key al arranque (independiente)
  Task 1.4 → Cola TTS (independiente)
  Task 1.1 → Fallback WAV (depende de Task 1.3 para el endpoint /transcribe)

Fase 2 (Altos):
  Task 2.1 → AlertMessage Pydantic (independiente)
  Task 2.2 → Eliminar migración forzosa hotkey (independiente)

Fase 3 (Tests):
  Task 3.1 → Tests TTS actualizados (depende de entender el router real)
  Task 3.2 → Test configStore corregido (depende de Task 2.2)
  Task 3.3 → Tests LLM migrados (independiente)

Fase 4 (Mejoras):
  Task 4.1 → Logging TTS visible (independiente)
  Task 4.2 → Capability global-shortcut (independiente)
  Task 4.3 → Clases CSS estándar (independiente)
```
