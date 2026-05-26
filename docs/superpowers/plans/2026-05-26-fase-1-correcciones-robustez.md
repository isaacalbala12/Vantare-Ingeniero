# Plan de Implementación: Fase 1 + Fase 6 — Correcciones Robustez y Unificación

> **Para agentic workers:** REQUIRED SUB-SKILL: Usar `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para implementar este plan tarea por tarea. Los pasos usan sintaxis checkbox (`- [ ]`) para tracking.

**Objetivo:** Completar las correcciones de robustez restantes (timeouts, fallbacks, unificación de clientes LLM) y las tareas pendientes de Fase 6 que no están verificadas.

**Arquitectura:** 8 tareas independientes que tocan backend (Python/FastAPI) y frontend (React/TypeScript). Cada tarea es autocontenida y puede ejecutarse en paralelo con las demás.

**Tech Stack:** Python 3.12+ (httpx, OpenAI SDK, FastAPI, Pydantic v2), TypeScript 5+ (React 19, Zustand), Shell scripting

**Pre-condiciones:** 
- Fase 0b completada (usePTT.ts compila limpio ✅)
- Fases 6.6-6.10 verificadas (edge-tts, GEMINI_API_KEY, timeout TTS, truncamiento, global-shortcut ✅)
- Fase 0 (WebSocket telemetría) ya implementada en su mayoría

---

## Análisis de Estado Actual

### ✅ Ya implementado (verificado):

| Tarea | Estado | Archivo | Detalle |
|-------|--------|---------|---------|
| T0.1-T0.4 | ✅ | `websocket.py`, `main.py`, `useWebSocket.ts` | Pipeline telemetría completo (echo frontend↔backend) |
| T1.2 | ✅ | `backend/src/config.py:36` | `PORT: int = 8008` |
| T1.3 | ✅ | `frontend/src/hooks/useWebSocket.ts:33,47` | Cola TTS con `ttsQueueRef` + `processTtsQueue` |
| T1.7 | ✅ | `backend/src/routers/websocket.py:117-118` | Salta ciclo si `manager.active_connections` vacío |
| T1.9 | ✅ | `backend/src/models/messages.py:52-54` | `severity`, `ttl`, `dismissable` ya en `AlertMessage` |
| T1.10 | ✅ | `frontend/src/store/config.ts:108` | `parsed.pttHotkey ?? "Ctrl+Shift+Space"` (no sobrescribe) |
| T6.6-T6.10 | ✅ | Varios | edge-tts, GEMINI, timeout TTS, truncamiento, global-shortcut |

### ❌ Pendiente de implementar:

| Tarea | Prioridad | Archivos | Descripción |
|-------|-----------|----------|-------------|
| **T1.5** | 🔴 ALTA | `backend/src/intelligence/llm_client.py` | Timeout en VLLMClient (25s total) |
| **T1.4** | 🔴 ALTA | `frontend/src/App.tsx`, `frontend/src/services/api.ts` | Timeout HTTP frontend (15s /ask, 5s /health) |
| **T6.4** | 🟡 MEDIA | `backend/src/services/llm_service.py`, `backend/src/intelligence/llm_client.py` | Unificar 2 clientes LLM en 1 |
| **T1.1** | 🟡 MEDIA | `frontend/src/App.tsx` | Fallback WAV cuando SpeechRecognition no disponible |
| **T0.5** | 🟢 BAJA | `backend/qa_test_script.py` | Test integración WebSocket telemetría |
| **T1.6** | 🟢 BAJA | `frontend/src/components/RadioOverlay.tsx` | Selectores Zustand finos (evitar re-render 20Hz) |
| **T1.8** | 🟢 BAJA | `frontend/src/components/ConfigTab.tsx` | Validación IP/puerto/hotkey |
| **T6.11** | 🟢 BAJA | `backend/src/services/lmu_api.py` | TTL en caches (detectar obsolescencia) |

---

## Task 1: Timeout en VLLMClient (T1.5)

**Archivo:** `backend/src/intelligence/llm_client.py:49-56`

**Problema:** El `AsyncOpenAI` se crea sin timeout explícito. Si el LLM se cuelga, la tarea queda bloqueada para siempre.

**Solución:** Añadir `timeout=httpx.Timeout(25.0, connect=10.0, read=20.0)` al constructor de `AsyncOpenAI`.

### Step 1: Añadir timeout al cliente OpenAI

En `backend/src/intelligence/llm_client.py`, modificar el método `_get_client()`:

```python
# Líneas 49-56 actuales:
def _get_client(self) -> AsyncOpenAI:
    """Devuelve (y cachea) el cliente OpenAI asíncrono."""
    if self._client is None:
        self._client = AsyncOpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
        )
    return self._client

# Debe quedar:
def _get_client(self) -> AsyncOpenAI:
    """Devuelve (y cachea) el cliente OpenAI asíncrono con timeout."""
    if self._client is None:
        import httpx
        self._client = AsyncOpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=httpx.Timeout(25.0, connect=10.0, read=20.0),
        )
    return self._client
```

### Step 2: Verificar importación de httpx

El archivo ya importa `httpx` en la línea 7 (`import httpx`). No se necesita añadir import.

### Step 3: Ejecutar tests existentes

```bash
cd /home/isaac-albala/Vantare-Ingeniero/backend && .venv/bin/python -m pytest tests/ -v -k "llm" 2>&1
```

### Step 4: Commit

```bash
git add backend/src/intelligence/llm_client.py
git commit -m "fix: añadir timeout httpx.Timeout(25s) al AsyncOpenAI en VLLMClient"
```

---

## Task 2: Timeout en llamadas HTTP del frontend (T1.4)

**Archivos:** 
- `frontend/src/App.tsx:237-250` (handleTextSubmit)
- `frontend/src/services/api.ts` (getHealth)

**Problema:** Las llamadas `fetch()` no tienen timeout. Si el backend cuelga, la UI se congela.

**Solución:** Envolver cada `fetch()` con `AbortController` + `setTimeout`.

### Step 1: Añadir timeout a getHealth en api.ts

En `frontend/src/services/api.ts`, modificar `getHealth`:

```typescript
export async function getHealth(baseUrl: string): Promise<any> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);
  
  try {
    const res = await fetch(`${baseUrl}/health`, {
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timeoutId);
  }
}
```

### Step 2: Añadir timeout a fetch /ask en App.tsx

En `frontend/src/App.tsx`, modificar `handleTextSubmit` (~línea 237-250):

```typescript
// Línea actual ~242:
const response = await fetch(`${baseUrl}/ask`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question: trimmed }),
});

// Debe quedar:
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 15000);

try {
  const response = await fetch(`${baseUrl}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: trimmed }),
    signal: controller.signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  // ... resto del código existente
} catch (err: any) {
  if (err.name === "AbortError") {
    console.warn("[App] Timeout en /ask (15s)");
    setRadioMode("IDLE");
    return;
  }
  throw err;
} finally {
  clearTimeout(timeoutId);
}
```

### Step 3: Verificar compilación TypeScript

```bash
cd /home/isaac-albala/Vantare-Ingeniero/frontend && npx tsc --noEmit 2>&1 | head -20
```

### Step 4: Commit

```bash
git add frontend/src/services/api.ts frontend/src/App.tsx
git commit -m "fix: añadir AbortController con timeout a fetch /ask (15s) y /health (5s)"
```

---

## Task 3: Unificar dos clientes LLM (T6.4)

**Archivos:**
- `backend/src/services/llm_service.py` (cliente legacy con httpx directo)
- `backend/src/intelligence/llm_client.py` (VLLMClient con OpenAI SDK)
- `backend/src/routers/llm.py` (usa `llamar_copiloto_stream`)

**Problema:** Hay DOS implementaciones separadas del cliente LLM:
1. `VLLMClient.ask_streaming_text()` en `llm_client.py` — usa `httpx.stream()` directamente
2. `llamar_copiloto_stream()` en `llm_service.py` — también usa `httpx.stream()` directamente, con código duplicado

**Solución:** Refactorizar `llamar_copiloto_stream()` para que use `VLLMClient` internamente, eliminando la duplicación.

### Step 1: Verificar que VLLMClient tiene método compatible

`VLLMClient.ask_streaming_text()` (línea 205) ya existe y devuelve `AsyncGenerator[str, None]`. La signatura es compatible con `llamar_copiloto_stream()`.

### Step 2: Inyectar VLLMClient en el módulo llm_service

Refactorizar `llamar_copiloto_stream()` para aceptar un cliente:

```python
# En backend/src/services/llm_service.py
# Eliminar líneas 216-297 (llamar_copiloto_stream completo)
# Reemplazar con:

from src.intelligence.llm_client import VLLMClient

async def llamar_copiloto_stream(
    pregunta: str, 
    contexto: dict, 
    chat_history: list = None,
    llm_client: VLLMClient = None,
):
    """Envía la pregunta del piloto y el contexto de carrera actual al LLM.
    
    Usa VLLMClient internamente. Si no se proporciona, crea uno nuevo.
    """
    if not settings.LLM_API_KEY:
        yield "Copiado piloto, pero no tengo conexión de red activa en boxes ahora mismo. Configura la clave de LLM_API_KEY para que pueda guiarte."
        return

    system_prompt = (
        "Eres el Ingeniero de Carrera Principal de un equipo de simracing. Tu piloto te está hablando "
        "por la radio de boxes/coche durante una sesión de Le Mans Ultimate.\n\n"
        "Debes responder de forma extremadamente concisa, directa y profesional (como un ingeniero de F1/WEC real, "
        "ej. 'Copiado, piloto', 'Entendido'). Usa un tono calmado, enfocado en datos, neumáticos, combustible y seguridad.\n\n"
        "Se te proporciona el contexto en tiempo real del coche. Usa estos datos para responder con precisión y brevedad.\n"
        "No divagues ni uses un lenguaje pomposo. Respuestas cortas, listas para oír en pista."
    )

    # Construir prompt completo (el contexto se pasa como mensaje de sistema adicional)
    contexto_json = json.dumps(contexto, ensure_ascii=False)
    full_prompt = f"{system_prompt}\n\nCONTEXTO ACTUAL DE CARRERA: {contexto_json}\n\n"
    
    if chat_history:
        for msg in chat_history[-6:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            full_prompt += f"\n[{role}]: {content}"
    
    full_prompt += f"\n[user]: {pregunta}"

    client = llm_client or VLLMClient()
    async for token in client.ask_streaming_text(full_prompt):
        yield token
```

### Step 3: Verificar que el router llm.py sigue funcionando

Revisar `backend/src/routers/llm.py` para confirmar que usa `llamar_copiloto_stream` correctamente.

### Step 4: Eliminar código duplicado

Si `llamar_copiloto_stream` ahora usa `VLLMClient`, el método `ask_streaming_text()` en `VLLMClient` (líneas 205-286) puede permanecer ya que es la implementación concreta. Pero verificar que el código SSE limpio (limpieza de etiquetas `<think>`, `</think>`, etc.) se mantenga.

### Step 5: Ejecutar tests

```bash
cd /home/isaac-albala/Vantare-Ingeniero/backend && .venv/bin/python -m pytest tests/ -v -k "llm" 2>&1
```

### Step 6: Commit

```bash
git add backend/src/services/llm_service.py
git commit -m "refactor: unificar llamar_copiloto_stream para usar VLLMClient internamente"
```

---

## Task 4: Fallback WAV cuando SpeechRecognition no disponible (T1.1)

**Archivo:** `frontend/src/App.tsx:179-218` (handlePTTEnd)

**Problema:** En Tauri/WebView2, `webkitSpeechRecognition` puede no estar disponible. Actualmente `handlePTTEnd` solo verifica si la transcripción está vacía y revierte a IDLE. Debería enviar el WAV al backend para transcripción ASR como fallback.

**Solución:** Si `isSpeechRecognitionAvailable === false` O la transcripción está vacía, enviar el blob WAV al endpoint `POST /transcribe`.

### Step 1: Modificar handlePTTEnd para enviar WAV

En `frontend/src/App.tsx`, modificar `handlePTTEnd` (líneas 179-218):

```typescript
const handlePTTEnd = async () => {
    const state = useAppStore.getState();
    if (state.radio.mode !== "LISTENING_PILOT") return;

    console.log("[App] PTT Finalizado — Procesando audio...");
    setRadioMode("THINKING_LLM");

    playBeep(false);

    const wavBlob = stopCapture();
    stopSpeechRecognition();

    await new Promise((resolve) => setTimeout(resolve, 200));

    let questionText = transcriptionRef.current.trim();
    
    // Fallback WAV: si SpeechRecognition no está disponible o no capturó texto
    if (!questionText && wavBlob && wavBlob.size > 0) {
      console.log("[App] SpeechRecognition no disponible o sin transcripción — enviando WAV para ASR");
      try {
        const config = useAppStore.getState().config;
        const baseUrl = `http://${config.vllmIP}:${config.serverPort}`;
        const formData = new FormData();
        formData.append("audio", wavBlob, "ptt_recording.wav");
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);
        
        const res = await fetch(`${baseUrl}/transcribe`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        
        if (res.ok) {
          const data = await res.json();
          questionText = (data.text || "").trim();
        }
      } catch (err) {
        console.warn("[App] Fallback ASR falló:", err);
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

### Step 2: Crear endpoint /transcribe en el backend

Crear archivo `backend/src/routers/transcribe.py`:

```python
import logging
from fastapi import APIRouter, UploadFile, File

logger = logging.getLogger("vantare.transcribe")

router = APIRouter()

@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Endpoint placeholder para transcripción ASR de audio WAV.
    
    Por ahora devuelve texto vacío. En el futuro:
    - Whisper local (faster-whisper)
    - O API cloud (Deepgram, Azure Speech)
    """
    logger.info(f"Received audio for transcription: {audio.filename} ({audio.content_type})")
    
    # Placeholder: leer el audio pero no transcribir aún
    _ = await audio.read()
    
    return {"text": ""}
```

### Step 3: Registrar router en main.py

En `backend/src/main.py`, añadir:

```python
from src.routers.transcribe import router as transcribe_router
# ...
app.include_router(transcribe_router)
```

### Step 4: Commit

```bash
git add frontend/src/App.tsx backend/src/routers/transcribe.py backend/src/main.py
git commit -m "feat: fallback WAV a /transcribe cuando SpeechRecognition no disponible"
```

---

## Task 5: Test de integración WebSocket (T0.5)

**Archivo:** `backend/qa_test_script.py`

**Problema:** No hay test automatizado que verifique el pipeline completo de telemetría frontend→backend.

**Solución:** Script Python que:
1. Conecta WebSocket al backend
2. Envía telemetría simulada (formato LMU)
3. Verifica que `/health` reporte `frontend_telemetry.received: true`

### Step 1: Crear script de test

Modificar/extender `backend/qa_test_script.py` con una función `test_websocket_telemetry()`:

```python
import asyncio
import json
import websockets
import httpx

async def test_websocket_telemetry():
    """Verifica que el backend recibe y procesa telemetría del frontend vía WebSocket."""
    base_url = "http://127.0.0.1:8008"
    ws_url = "ws://127.0.0.1:8008/ws"
    
    # 1. Conectar WebSocket
    async with websockets.connect(ws_url) as ws:
        print("[TEST] WebSocket conectado")
        
        # 2. Construir payload de telemetría simulada
        telemetry_payload = {
            "event": "telemetry",
            "data": {
                "timestamp": 1234567890.0,
                "player": {
                    "speed": 250.0,
                    "fuel": 45.5,
                    "current_lap": 5,
                    "place": 3,
                    "in_pits": False,
                },
                "engine": {
                    "rpm": 8500,
                    "gear": 5,
                },
                "tyres": {
                    "wear": [0.15, 0.18, 0.12, 0.14],
                },
            }
        }
        
        # 3. Enviar telemetría
        await ws.send(json.dumps(telemetry_payload))
        await asyncio.sleep(0.5)  # Dar tiempo al backend
        
        # 4. Verificar health
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{base_url}/health")
            assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
            data = resp.json()
            
            ft = data.get("frontend_telemetry", {})
            assert ft.get("received") == True, (
                f"frontend_telemetry.received debería ser true, es {ft}"
            )
        
        print("[TEST] ✅ Pipeline WebSocket verificado: telemetría recibida por backend")
        return True

if __name__ == "__main__":
    result = asyncio.run(test_websocket_telemetry())
    print(f"Resultado: {'✅ PASÓ' if result else '❌ FALLÓ'}")
```

### Step 2: Ejecutar test

```bash
# Con backend corriendo en otra terminal
cd /home/isaac-albala/Vantare-Ingeniero/backend && .venv/bin/python qa_test_script.py
```

### Step 3: Commit

```bash
git add backend/qa_test_script.py
git commit -m "test: añadir test de integración WebSocket telemetría"
```

---

## Task 6: Selectores finos Zustand en RadioOverlay (T1.6)

**Archivo:** `frontend/src/components/RadioOverlay.tsx`

**Problema:** El componente se suscribe al store completo, causando re-render cada 50ms (20Hz de telemetría).

**Solución:** Usar selectores individuales para cada slice.

### Step 1: Reemplazar suscripción global por selectores

En `frontend/src/components/RadioOverlay.tsx`, localizar el hook `useAppStore()` y reemplazar:

```typescript
// ANTES (suscripción al store completo — re-render a 20Hz):
const store = useAppStore();

// DESPUÉS (selectores individuales — solo re-render cuando cambia el slice relevante):
const speed = useAppStore((s) => s.speed);
const rpm = useAppStore((s) => s.rpm);
const gear = useAppStore((s) => s.gear);
const fuel = useAppStore((s) => s.fuel);
const lap = useAppStore((s) => s.lap);
const position = useAppStore((s) => s.position);
const gaps = useAppStore((s) => s.gaps);
const tyreWear = useAppStore((s) => s.tyreWear);
const radioMode = useAppStore((s) => s.radio.mode);
const currentTokens = useAppStore((s) => s.radio.currentTokens);
const latestAdvice = useAppStore((s) => s.radio.latestAdvice);
const latestAlert = useAppStore((s) => s.radio.latestAlert);
const wsStatus = useAppStore((s) => s.connectivity.wsStatus);
const screen = useAppStore((s) => s.screen);

// Y reemplazar todas las referencias a store.xxx → variable directa
```

### Step 2: Verificar compilación

```bash
cd /home/isaac-albala/Vantare-Ingeniero/frontend && npx tsc --noEmit 2>&1 | grep -i error | head -20
```

### Step 3: Commit

```bash
git add frontend/src/components/RadioOverlay.tsx
git commit -m "perf: usar selectores Zustand individuales en RadioOverlay para evitar re-renders a 20Hz"
```

---

## Task 7: Validación de configuración (T1.8)

**Archivo:** `frontend/src/components/ConfigTab.tsx`

**Problema:** No hay validación de IP, puerto, ni hotkey al guardar configuración.

**Solución:** Añadir validación en el handler de guardado.

### Step 1: Añadir validación antes de guardar

En el handler `onSave` de `ConfigTab.tsx`, añadir:

```typescript
const validateConfig = (config: AppConfig): string | null => {
  // Validar IP
  const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$|^localhost$/;
  if (!ipRegex.test(config.vllmIP)) {
    return "IP inválida. Usa formato 192.168.1.100 o 'localhost'";
  }
  
  // Validar puerto
  if (config.serverPort < 1 || config.serverPort > 65535) {
    return "Puerto inválido. Debe estar entre 1 y 65535";
  }
  
  // Validar hotkey (debe contener al menos un modificador + una tecla)
  const hotkeyRegex = /^(Ctrl|Alt|Shift|Meta)\+[\w]$/;
  if (!hotkeyRegex.test(config.pttHotkey)) {
    return "Hotkey inválida. Formato: Ctrl+Shift+X";
  }
  
  return null; // Válido
};

// En el handler de guardado:
const error = validateConfig(newConfig);
if (error) {
  // Mostrar error en UI (setError o toast)
  return;
}
// ... guardar configuración
```

### Step 2: Commit

```bash
git add frontend/src/components/ConfigTab.tsx
git commit -m "feat: añadir validación de IP, puerto y hotkey en ConfigTab"
```

---

## Task 8: Cache TTL en lmu_api.py (T6.11)

**Archivo:** `backend/src/services/lmu_api.py`

**Problema:** Los caches (`_weather_cache`, `_strategy_usage_cache`, `_garage_wear_cache`) no tienen timestamp. Los consumidores no pueden saber si los datos están obsoletos.

**Solución:** Añadir atributos `_last_updated` a cada cache y exponerlos en `get_cache_sizes()`.

### Step 1: Añadir timestamps a los caches

```python
# Líneas 12-14 — añadir timestamps:
_weather_cache: dict = {}
_strategy_usage_cache: dict = {}
_garage_wear_cache: dict = {}
_weather_updated: float = 0.0
_strategy_updated: float = 0.0
_garage_updated: float = 0.0
```

### Step 2: Actualizar timestamps al refrescar caches

En la función `poll_api()`, después de cada swap atómico (~línea 156):

```python
# Después de línea 156 (_garage_wear_cache = new_garage):
if new_weather is not None:
    global _weather_updated
    _weather_updated = current_time
if new_strategy is not None:
    global _strategy_updated
    _strategy_updated = current_time
if new_garage is not None:
    global _garage_updated
    _garage_updated = current_time
```

### Step 3: Exponer en get_cache_sizes()

```python
def get_cache_sizes() -> dict[str, int]:
    """Cantidad de entradas en los caches con timestamps. Útil para diagnóstico."""
    with _cache_lock:
        return {
            "weather": len(_weather_cache),
            "strategy_usage": len(_strategy_usage_cache),
            "garage_wear": len(_garage_wear_cache),
            "drivers": len(_strategy_usage_cache),
            "brakes": len(_garage_wear_cache),
            "weather_age_s": time.monotonic() - _weather_updated if _weather_updated else -1,
            "strategy_age_s": time.monotonic() - _strategy_updated if _strategy_updated else -1,
            "garage_age_s": time.monotonic() - _garage_updated if _garage_updated else -1,
        }
```

### Step 4: Commit

```bash
git add backend/src/services/lmu_api.py
git commit -m "feat: añadir timestamps a caches LMU API para detectar obsolescencia"
```

---

## Verificación Global

Al finalizar todas las tareas, ejecutar:

```bash
# Backend: tests + smoke test
cd /home/isaac-albala/Vantare-Ingeniero/backend
.venv/bin/python -m pytest tests/ -v 2>&1 | tail -5
.venv/bin/python qa_test_script.py

# Frontend: TypeScript + tests
cd /home/isaac-albala/Vantare-Ingeniero/frontend
npx tsc --noEmit 2>&1 | grep -c error  # Debe ser 0
npx vitest run 2>&1 | tail -3
```

---

## Dependencias entre tareas

```
T1.5 (timeout VLLMClient) ──── independiente
T1.4 (timeout frontend)  ──── independiente
T6.4 (unificar LLM)      ──── independiente
T1.1 (fallback WAV)      ──── independiente
T0.5 (test integración)  ──── requiere backend corriendo
T1.6 (selectores Zustand)─── independiente
T1.8 (validación config) ──── independiente
T6.11 (cache TTL)        ──── independiente
```

**Todas las tareas son independientes entre sí y pueden ejecutarse en paralelo.**

---

## Orden recomendado de ejecución

1. **T1.5** (timeout LLM) — 🔴 crítico, evita bloqueos
2. **T1.4** (timeout frontend) — 🔴 crítico, evita UI congelada
3. **T6.4** (unificar LLM) — 🟡 simplifica código
4. **T1.1** (fallback WAV) — 🟡 mejora experiencia
5. **T0.5** (test integración) — 🟢 validación
6. En paralelo: T1.6, T1.8, T6.11 — 🟢 baja prioridad
