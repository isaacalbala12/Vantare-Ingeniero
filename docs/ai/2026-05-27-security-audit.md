# Security Audit — Vantare Ingeniero IA
**Fecha:** 27 Mayo 2026
**Scope:** Full repo (backend Python + frontend React/TS + Rust Tauri)
**Tipo:** AI-assisted static review (no penetration test)

---

## Resumen

| Severidad | Encontrados | Reportados |
|:---------:|:-----------:|:----------:|
| 🔴 CRITICAL | 0 | 0 |
| 🟠 HIGH | 0 | 0 |
| 🟡 MEDIUM | 2 | 2 |
| 🟢 LOW | 3 | 3 |

**Veredicto:** El código no tiene vulnerabilidades explotables en su contexto de uso previsto (aplicación local de escritorio, sin exposición a internet, sin autenticación multiusuario). Los hallazgos son principalmente de higiene y buenas prácticas.

---

## Attack Surface Map

```
PUBLIC    GET  /health           → health info              (health.py:7)
PUBLIC    GET  /tts?text=        → TTS synthesis            (tts.py:12)
PUBLIC    POST /ask              → LLM question             (llm.py:21)
PUBLIC    POST /transcribe       → audio upload             (transcribe.py:9)
PUBLIC    GET  /history          → race history             (history.py:14)
PUBLIC    WS   /ws               → main WebSocket           (websocket.py:237)
PUBLIC    WS   /ws/sidecar       → sidecar WebSocket        (websocket.py:204)
```

**No authentication on any endpoint.** By design — aplicación local de escritorio, no servicio multiusuario.

---

## Findings

### 🟡 M1 — .env versionado en git (MEDIUM)

**Archivo:** `backend/.env`
**Línea:** N/A (trackeado por git)

**Problema:**
```bash
$ git ls-files '*.env'
backend/.env   # ← TRACKEADO
```

El archivo `.env` contiene la configuración del entorno incluyendo `LLM_API_KEY`, `LLM_BASE_URL`, y otros valores. Aunque la API key actual (`REDACTED`) es un identificador local (no es una clave real de un servicio cloud), la práctica de trackear `.env` en git es un anti-patrón de seguridad porque:

1. Si en el futuro se añade una API key real (ElevenLabs, Groq, OpenAI), quedaría expuesta en el historial de git
2. Dificulta rotar claves sin exponer las anteriores
3. Complica el uso de diferentes configuraciones por entorno (dev/staging/prod)

**Fix:** 
1. Añadir `backend/.env` a `.gitignore`
2. Renombrar `backend/.env` → `backend/.env.example` con valores placeholder
3. Mantener un `.env` local no versionado

```bash
# backend/.gitignore (añadir)
backend/.env
```

---

### 🟡 M2 — Endpoint /transcribe sin límite de tamaño (MEDIUM)

**Archivo:** `backend/src/routers/transcribe.py:10-22`

**Problema:**
```python
@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    _ = await audio.read()  # Sin límite de tamaño
```

El endpoint acepta cualquier archivo de audio sin restringir tamaño ni tipo MIME. En un contexto local no es explotable remotamente, pero si el backend se expusiera accidentalmente (Cloudflare tunnel mal configurado), un atacante podría:
1. Enviar un archivo enorme → OOM (memory exhaustion)
2. Enviar binarios no-audio → comportamiento indefinido si se integra Whisper

**Riesgo actual:** Bajo (solo localhost y es placeholder). **Riesgo futuro:** Medio (cuando se integre Whisper real).

**Fix:**
```python
from fastapi import HTTPException
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB

@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    if audio.content_type and not audio.content_type.startswith("audio/"):
        raise HTTPException(400, "Tipo de archivo no soportado")
    contents = await audio.read()
    if len(contents) > MAX_AUDIO_SIZE:
        raise HTTPException(413, "Archivo demasiado grande")
```

---

### 🟢 L1 — Rust unwrap() sin contexto (LOW)

**Archivo:** `frontend/src-tauri/src/main.rs:93,98,134`

**Problema:**
```rust
.icon(app.default_window_icon().unwrap().clone())  // línea 93
app.state::<BackendChild>().0.lock().unwrap().take()  // línea 98
state.0.lock().unwrap().take()  // línea 134
```

Tres llamadas a `.unwrap()` que pueden causar panic en runtime si:
- El icono por defecto no está configurado (línea 93)
- El Mutex está poisoned (líneas 98, 134)

**Fix:**
```rust
// línea 93
.icon(app.default_window_icon()
    .expect("default_window_icon debe estar configurado en tauri.conf.json")
    .clone())

// líneas 98, 134 — usar if let Ok en vez de unwrap
if let Ok(mut guard) = app.state::<BackendChild>().0.lock() {
    if let Some(child) = guard.take() {
        let _ = child.kill();
    }
}
```

---

### 🟢 L2 — CORS allow_methods/allow_headers permisivo (LOW)

**Archivo:** `backend/src/main.py:258-272`

**Problema:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["tauri://localhost", "http://localhost:1420", ...],
    allow_methods=["*"],   # ← Permite cualquier método HTTP
    allow_headers=["*"],   # ← Permite cualquier header
)
```

Aunque `allow_origins` tiene una allowlist correcta (solo localhost/Tauri), permitir todos los métodos y headers es más permisivo de lo necesario.

**Riesgo:** Bajo. Los orígenes están restringidos a localhost.

**Fix:**
```python
allow_methods=["GET", "POST", "OPTIONS"],
allow_headers=["Content-Type", "Authorization"],
```

---

### 🟢 L3 — Sin límite de tasa en endpoints (LOW)

**Problema:** Ninguno de los endpoints públicos tiene rate limiting. En un contexto local no hay riesgo de brute force, pero si se expone el backend a través de Cloudflare Tunnel, un atacante podría:
- Enviar peticiones masivas a `/tts` para consumir cuota de Edge TTS (Azure)
- Enviar peticiones masivas a `/ask` para consumir recursos del LLM

**Riesgo actual:** Nulo (solo localhost). **Riesgo si se expone:** Medio.

**Fix:** Añadir `slowapi` o middleware de rate limiting si el backend se expone públicamente.

---

## LLM Security Assessment

### Surface: Prompt Injection

| Vector | Estado | Riesgo |
|--------|:------:|:------:|
| User question → system prompt | El `pilot_question` del piloto se inyecta directamente en el prompt del LLM (`engine.py:155`) | 🟢 Bajo |
| RAG data (ChromaDB) | Datos históricos embedidos, no texto del usuario | 🟢 Bajo |
| Telemetry data | Datos estructurados del juego, no controlables por el usuario | 🟢 Bajo |

**Análisis:** El LLM se usa con un system prompt fijo + telemetría estructurada + pregunta del piloto. La pregunta del piloto va en la posición de `user` message (esperada), no en system prompt. El LLM solo puede ejecutar tool calls para acciones UI (mostrar/ocultar paneles). Sin acceso a base de datos, shell, red, o datos sensibles.

**Excessive Agency (OWASP LLM #8):** No aplica. Las tool calls solo controlan acciones UI inofensivas.

**Improper Output Handling (OWASP LLM #5):** No aplica. La salida del LLM va a TTS (audio), no se renderiza como HTML ni se ejecuta.

### Surface: API Key Exposure

La `LLM_API_KEY` viaja en el header `Authorization: Bearer REDACTED` hacia el LLM a través de Cloudflare Tunnel. Como es una API key local/identificador, el riesgo es nulo. Pero:

- Si se usara una API key real de Groq/OpenAI, el tráfico viajaría por Cloudflare Tunnel sin cifrado adicional extremo-a-extremo
- **Recomendación:** Si se usan API keys cloud, implementar un proxy inverso con TLS propio

---

## Data Privacy Assessment

| Servicio | Datos enviados | Destino |
|----------|---------------|---------|
| Edge TTS | Texto de las alertas/consejos | Azure Cognitive Services (Microsoft) |
| LLM (Qwen) | Prompt completo (telemetría + pregunta) | PC local (GPU) |
| ChromaDB RAG | Embeddings locales | Local (disco) |
| Cloudflare Tunnel | Tráfico LLM | PC LLM remoto (si aplica) |

**Nota:** Edge TTS envía el texto de las alertas a servidores de Microsoft Azure. Si la estrategia de carrera contiene datos sensibles (nombres de pilotos, configuración del coche), esto es una consideración de privacidad. Alternativa: Piper TTS (local) elimina esta dependencia.

---

## Dependencies — Known CVEs

No se encontraron ficheros `Dockerfile`, `.github/workflows/`, ni dependencias con CVEs conocidos en las versiones utilizadas:

| Dependencia | Versión | CVE conocidos |
|-------------|:-------:|:--------------:|
| FastAPI | ≥0.110 | Sin CVEs activos en 2026-05 |
| Tauri v2 | 2.x | Sin CVEs públicos conocidos |
| edge-tts | ≥7.0 | Sin CVEs |
| chromadb | última | Sin CVEs públicos |
| React 19 | 19 | Sin CVEs activos |

---

## Disclaimer

> Esta es una revisión de seguridad asistida por IA, no una prueba de penetración. Detecto patrones de vulnerabilidad comunes y actuales; puedo omitir bugs criptográficos sutiles, canales laterales de timing, y problemas que requieren observación en runtime. Para cualquier sistema que maneje pagos, PII, o credenciales de producción, contrata a una firma de seguridad cualificada. Úsame como segundo pase rápido, no como tu única línea de defensa.
