# Edge TTS como Motor de Voz Principal — Correcciones

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar Edge TTS configurado y funcionando como motor de voz principal del Ingeniero de IA, resolviendo los 6 problemas diagnosticados.

**Architecture:** Correcciones en 3 capas: (1) configuración/entorno, (2) servicio backend, (3) frontend. Se aplican en orden de criticidad descendente. Cada corrección es independiente y testeable por separado.

**Tech Stack:** Python 3.12+, FastAPI, edge-tts 7.2.8, React 19 + TypeScript

---

### Task 1: 🔴 Corregir TTS_BACKEND en .env

**Files:**
- Modify: `backend/.env:23`

**Análisis:** Actualmente `TTS_BACKEND=gemini` pero `GEMINI_API_KEY` está comentada, creando una contradicción donde el backend configurado apunta a un servicio no inicializado. Edge TTS solo funciona como fallback.

- [ ] **Step 1: Cambiar TTS_BACKEND de gemini a edge**

Cambiar línea 23 de `TTS_BACKEND=gemini` a `TTS_BACKEND=edge`. También limpiar las líneas comentadas de Gemini (29-32) para evitar confusiones futuras.

Cambio en `backend/.env`:
```diff
 # TTS Backend (por defecto: edge)
-TTS_BACKEND=gemini
+TTS_BACKEND=edge

 # ElevenLabs TTS (opcional, descomentar y añadir clave para activar)
 # ELEVENLABS_API_KEY="tu-api-key-aqui"
 # ELEVENLABS_VOICE_ID="pNInz6obpgDQGcFmaJgB"

-# Gemini TTS (opcional, descomentar y añadir clave para activar)
-# TTS_BACKEND=gemini
-# GEMINI_API_KEY="AIzaSyA--zxhdiK6enjGbi2l0aK9okzi5Xhu6w0"
-# GEMINI_TTS_VOICE="Kore"
```

- [ ] **Step 2: Verificar que el backend arranca con Edge TTS como primary**

Ejecutar:
```bash
cd "C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\backend"
python run_dev.py --port 8000
```

Buscar en los logs:
```
EdgeTTSService initialized (voice=es-ES-AlvaroNeural)
TTS backend activo: edge. Edge=OK Piper=NO ElevenLabs=NO Gemini=NO
```

**Riesgo:** Ninguno. El cambio es una reasignación de variable de entorno. Edge TTS ya está instalado (versión 7.2.8).

**Tests afectados:** Ninguno. `test_tts.py` usa servicios mockeados, no lee `.env`.

---

### Task 2: 🔴 Declarar edge-tts en pyproject.toml

**Files:**
- Modify: `backend/pyproject.toml:10-18`

**Análisis:** `edge-tts==7.2.8` está instalado en el entorno actual pero no está declarado como dependencia. En un fresh virtualenv o en un build de PyInstaller, no se instalará, causando que `ImportError` en el lifespan deje Edge TTS como `None` silenciosamente.

- [ ] **Step 1: Añadir edge-tts a la sección dependencies**

En `backend/pyproject.toml`, añadir `"edge-tts>=7.0.0"` después de `"openai>=1.60.0"` (o en orden alfabético, antes de fastapi):

```diff
 dependencies = [
+    "edge-tts>=7.0.0",
     "fastapi>=0.110.0",
```

- [ ] **Step 2: Verificar que se resuelve correctamente**

```bash
cd "C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\backend"
pip install -e .
python -c "import edge_tts; print(edge_tts.__version__)"
```

Esperado: `7.2.8` (o cualquier versión >= 7.0.0)

**Riesgo:** Bajo. `edge-tts` es una librería pura Python sin dependencias nativas. No hay conflictos conocidos con las otras dependencias del proyecto.

**Tests afectados:** Ninguno directamente. Pero garantiza que builds futuros incluyan edge-tts.

---

### Task 3: 🔴 Eliminar GEMINI_API_KEY hardcodeada de config.py

**Files:**
- Modify: `backend/src/config.py:44`

**Análisis:** `GEMINI_API_KEY` tiene un valor por defecto hardcodeado (`AIzaSyA--zxhdiK6enjGbi2l0aK9okzi5Xhu6w0`) en `config.py`. Esto es un riesgo de seguridad: la clave está expuesta en el repositorio y cualquier persona con acceso al código puede usarla.

- [ ] **Step 1: Cambiar el default de GEMINI_API_KEY a string vacío**

En `backend/src/config.py`, línea 44:
```diff
-    GEMINI_API_KEY: str = "AIzaSyA--zxhdiK6enjGbi2l0aK9okzi5Xhu6w0"
+    GEMINI_API_KEY: str = ""
```

- [ ] **Step 2: Verificar que el backend arranca sin error**

```bash
cd "C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\backend"
python run_dev.py --port 8000
```

Buscar en logs:
```
GeminiTTSService no configurado (GEMINI_API_KEY vacía)
TTS backend activo: edge. Edge=OK Piper=NO ElevenLabs=NO Gemini=NO
```

- [ ] **Step 3: Verificar que gemini service queda como None (sin crash)**

Ejecutar:
```bash
cd "C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\backend"
python -c "
from src.config import settings
print('GEMINI_API_KEY:', repr(settings.GEMINI_API_KEY))
assert settings.GEMINI_API_KEY == '', 'Debería estar vacía'
print('OK')
"
```

Esperado:
```
GEMINI_API_KEY: ''
OK
```

**Riesgo:** 
- Si alguien estaba usando la API key hardcodeada (mal hábito), dejará de funcionar. Pero usuarios legítimos deben configurar su propia key en `.env`.
- El bloque `if settings.GEMINI_API_KEY:` en main.py línea 138 maneja correctamente el caso de string vacío (no inicializa el servicio, loguea aviso).

**Tests afectados:** Ninguno. Los tests no referencian `GEMINI_API_KEY`.

---

### Task 4: 🟡 Añadir timeout a EdgeTTSService.synthesize()

**Files:**
- Modify: `backend/src/services/edge_tts_service.py:28-44`

**Análisis:** `edge_tts.Communicate` no tiene timeout interno. Si Azure Cognitive Services tarda en responder o hay una pérdida de paquete, la corrutina puede quedarse colgada indefinidamente, bloqueando la request HTTP a `/tts`.

- [ ] **Step 1: Añadir timeout de 30 segundos con asyncio.wait_for**

En `backend/src/services/edge_tts_service.py`:

```diff
 import logging
+import asyncio

 import edge_tts

 logger = logging.getLogger("vantare.edge_tts")
 
 class EdgeTTSService:
     """..."""
 
     def __init__(self, voice: str = "es-ES-AlvaroNeural") -> None:
         self._voice = voice
         logger.info("EdgeTTSService initialized (voice=%s)", voice)
 
     async def synthesize(self, text: str) -> bytes:
         """..."""
         if not text or not text.strip():
             return b""
 
         communicate = edge_tts.Communicate(text, self._voice)
         audio_bytes = b""
-        async for chunk in communicate.stream():
-            if chunk["type"] == "audio":
-                audio_bytes += chunk["data"]
+        try:
+            async for chunk in communicate.stream():
+                if chunk["type"] == "audio":
+                    audio_bytes += chunk["data"]
+        except asyncio.TimeoutError:
+            logger.error("Edge TTS timeout después de 30 segundos (%d chars)", len(text))
+            raise
```

Y luego **envolver la llamada asíncrona completa** en un timeout. Pero `asyncio.wait_for` no se puede usar directamente en un `async for`. La solución correcta es envolver el bloque completo:

```python
async def synthesize(self, text: str) -> bytes:
    if not text or not text.strip():
        return b""

    communicate = edge_tts.Communicate(text, self._voice)
    audio_bytes = b""

    async def _stream():
        nonlocal audio_bytes
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        return audio_bytes

    try:
        audio_bytes = await asyncio.wait_for(_stream(), timeout=30.0)
        logger.info(
            "Edge TTS: %d chars -> %d bytes MP3 (voice=%s)",
            len(text),
            len(audio_bytes),
            self._voice,
        )
        return audio_bytes
    except asyncio.TimeoutError:
        logger.error("Edge TTS timeout tras 30s (%d chars)", len(text))
        raise
```

- [ ] **Step 2: Verificar que el timeout funciona**

Ejecutar los tests existentes de TTS para confirmar que no se rompen:
```bash
cd "C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\backend"
pytest tests/test_tts.py -v
```

Esperado: Todos los tests PASS.

- [ ] **Step 3: Verificar integración rápida (manual)**

Arrancar backend:
```bash
cd "C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\backend"
python run_dev.py --port 8000
```

Hacer request TTS:
```bash
curl "http://127.0.0.1:8000/tts?text=Hola%20piloto" -o test_tts_output.mp3
```

Esperado: archivo `test_tts_output.mp3` no vacío (> 0 bytes).

**Riesgo:** Muy bajo. El timeout de 30s es generoso (Edge TTS típicamente responde en 1-3s). Si hay un falso positivo, solo aplica cuando Azure está realmente inaccesible.

**Tests afectados:** Los tests existentes en `test_tts.py` mockean el servicio, no se ven afectados por el timeout real. Se podría considerar añadir un test de timeout si se desea, pero no es crítico.

---

### Task 5: 🟡 Alinear puerto entre backend y frontend

**Files:**
- Modify: `backend/.env:19`

**Análisis:** Hay 3 valores distintos de puerto:
- `config.py` default: `8008`
- `.env`: `PORT=8000` (sobrescribe)
- Frontend (config store): `serverPort` default `8008`

Para alinear, se cambia `.env` a `PORT=8008` para que coincida con el default del frontend y de `config.py`. Esto evita que el frontend tenga que configurar explícitamente el puerto.

- [ ] **Step 1: Cambiar PORT en .env de 8000 a 8008**

En `backend/.env`:
```diff
 HOST="127.0.0.1"
-PORT=8000
+PORT=8008
 DEBUG=false
```

- [ ] **Step 2: Verificar que el backend arranca en el puerto correcto**

```bash
cd "C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\backend"
python run_dev.py
```

El log debe mostrar:
```
Starting server on 127.0.0.1:8008...
```

**Riesgo:**
- Si el usuario tiene configuraciones locales que referencian `localhost:8000`, dejarán de funcionar.
- El frontend en Tauri conecta a `http://{vllmIP}:{serverPort}` donde `serverPort` por defecto es 8008, así que estará alineado automáticamente.
- `run_dev.py` también tiene `--port 8008` como default, consistente.

**Tests afectados:** Ninguno. Los tests usan TestClient de FastAPI y no dependen del puerto real.

---

### Task 6: 🟡 Alinear truncamiento de texto frontend con backend

**Files:**
- Modify: `frontend/src/hooks/useWebSocket.ts:55-56`

**Análisis:** El frontend trunca a 500 caracteres antes de enviar a `/tts`, pero el backend acepta hasta 2000. Esto limita artificialmente las respuestas de voz del ingeniero. Mensajes como análisis detallados de estrategia (>500 chars) se cortan innecesariamente.

- [ ] **Step 1: Cambiar el límite de 500 a 2000 caracteres**

En `frontend/src/hooks/useWebSocket.ts`, línea 55:

```diff
-    const ttsText = fullText.length > 500 ? fullText.slice(0, 497) + "..." : fullText;
+    const ttsText = fullText.length > 2000 ? fullText.slice(0, 1997) + "..." : fullText;
```

- [ ] **Step 2: Verificar que el frontend compila sin errores**

```bash
cd "C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\frontend"
npx tsc --noEmit
```

Esperado: Sin errores de TypeScript.

- [ ] **Step 3: Ejecutar tests del frontend**

```bash
cd "C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\frontend"
npx vitest run
```

Esperado: Todos los tests PASS.

**Riesgo:** Muy bajo. Es un cambio de constante numérica. El backend ya maneja correctamente el truncamiento a 2000.

**Tests afectados:** Los tests de filtros (`filters.test.ts`) prueban el filtrado de `---` pero no la longitud de truncamiento. Los tests de audio queue tampoco. No hay tests que validen el límite de 500, por lo que no se rompen.

---

## Self-Review

### 1. Spec coverage
- [x] **Task 1**: TTS_BACKEND=gemini → edge (.env)
- [x] **Task 2**: edge-tts no declarado en pyproject.toml → añadir dependencia
- [x] **Task 3**: GEMINI_API_KEY hardcodeada → eliminar default
- [x] **Task 4**: Sin timeout en edge_tts_service → añadir asyncio.wait_for
- [x] **Task 5**: Puerto inconsistente 8000 vs 8008 → alinear a 8008
- [x] **Task 6**: Truncamiento 500 vs 2000 → alinear a 2000

### 2. Placeholder scan
- [x] No placeholders, TBDs, or "implement later" found
- [x] Every step has complete code diff or exact commands

### 3. Type consistency
- [x] All imports and identifiers consistent across tasks
- [x] Method signatures unchanged
- [x] Settings field names unchanged (`TTS_BACKEND`, `EDGE_TTS_VOICE`, `GEMINI_API_KEY`, `PORT`)

---

## Orden de Implementación Recomendado

```
Paso  | Tarea  | Descripción                     | Depende de | Riesgo  | Tiempo est.
------|--------|---------------------------------|------------|---------|-------------
1     | Task 1 | .env: TTS_BACKEND=edge          | Ninguna    | Ninguno | 1 min
2     | Task 2 | pyproject.toml: edge-tts dep    | Ninguna    | Bajo    | 1 min
3     | Task 3 | config.py: GEMINI_API_KEY=""    | Ninguna    | Bajo    | 1 min
4     | Task 5 | .env: PORT=8008                 | Ninguna    | Bajo    | 1 min
5     | Task 4 | edge_tts_service: timeout       | Ninguna    | Bajo    | 5 min
6     | Task 6 | useWebSocket.ts: 500→2000       | Ninguna    | Bajo    | 1 min
```

**Nota:** Tasks 1-3-5 tocan el mismo archivo (.env). Se pueden agrupar en un solo cambio si se desea, pero se mantienen separadas para claridad de propósito.

**Verificación final integrada** (después de todas las tareas):
```bash
# Backend
cd "C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\backend"
pytest tests/test_tts.py -v

# Frontend
cd "C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\frontend"
npx vitest run

# Arranque manual
python run_dev.py
# Verificar logs: Edge=OK, TTS backend activo: edge
# curl http://127.0.0.1:8008/tts?text=Test -o test.mp3
```
