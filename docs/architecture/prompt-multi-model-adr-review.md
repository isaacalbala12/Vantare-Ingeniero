# Prompts — Revisión multi-modelo ADR-004

> **Diseño abierto (sin plan previo):** [`prompt-open-architecture-design.md`](prompt-open-architecture-design.md)

Copia el **Prompt maestro** a distintos modelos (Claude, GPT, Gemini, etc.). Añade al final **una variante de fase** si quieres profundizar en una fase concreta.

---

## Prompt maestro (revisión completa ADR + plan)

```markdown
# Rol

Eres un arquitecto de software senior especializado en sistemas en tiempo real, desktop apps y sim-racing telemetry. Debes ser crítico, concreto y honesto. No alabes el plan por defecto: busca fallos, alternativas mejores y riesgos ocultos.

# Contexto del producto — Vantare Ingeniero IA

**Qué es:** Aplicación desktop para **Le Mans Ultimate (LMU)** que actúa como ingeniero de pista / spotter por voz, en español, con IA conversacional (PTT).

**Stack actual:**
- **Frontend:** Tauri 2 + React 19 + TypeScript (overlay, config, PTT, cola de audio)
- **Backend:** Python 3.12 + FastAPI (~129 archivos en `backend/src/`)
- **Telemetría:** Lectura nativa Windows vía shared memory (`shared-telemetry` / pyLMUSharedMemory) a ~20 Hz — ADR-003, sin sidecar
- **Estrategia:** `shared-strategy/` + `StrategyService` (fuel, gaps, competidores, etc.)
- **Spotter:** `SpotterService` @ 20 Hz (proximidad lateral, multiclase)
- **Paridad CrewChief:** Port nativo en Python (`crewchief_events/` — ~25 módulos: flags, fuel, penalties, rain, pits, multiclass, etc.). **NO queremos ejecutar ni fork de CrewChiefV4**; queremos comportamiento lo más similar posible implementado en nuestro código.
- **IA:** LLM (PTT libre), triggers, preemption; RAG/ChromaDB opcional
- **Voz:** Edge TTS (+ Piper/Eleven/Gemini en dev), audio reproducido hoy en **React** (`HTMLAudioElement`, `GET /tts`, gates en TS)
- **Deploy:** PyInstaller empaquetado dentro del instalador Tauri (Windows)

**Objetivo de negocio (prioridad):**
1. **Lanzar algo estable lo antes posible**
2. **Corregir problemas arquitectónicos de verdad** (no solo parches)
3. **Paridad funcional CrewChief en LMU** (determinista) + diferencial Vantare (LLM, español, UI moderna)

**Problemas ya observados en producción:**
- Spotter detectaba bien en logs backend pero **no se oía** (desync config UI/backend, gates frontend, bugs en pipeline TTS React)
- Audio repartido entre frontend y backend → un bug TS = silencio total
- PyInstaller frágil (deploy parcial corrompe instalación)
- **Bug P0:** `CrewChiefGameStateLoop.on_frame` corre dentro de `telemetry_sender_loop` **por cada cliente WebSocket**, mientras el spotter corre en un loop global separado → CC no corre sin UI conectada y se duplica con N clientes
- LLM/TTS compiten en el mismo proceso/event loop que telemetría 20 Hz

**Restricciones no negociables:**
- ❌ No usar CrewChiefV4 como dependencia/runtime
- ✅ Sí portar/reutilizar lógica CC ya escrita en `crewchief_events/`
- ✅ Windows first (telemetría nativa LMU)
- ✅ Mantener LLM/PTT como diferenciador
- ⏱️ Preferir soluciones que permitan valor en pista en semanas, no reescritura total en meses

---

# Propuesta a evaluar — ADR-004 (dual-process)

## Arquitectura objetivo

```
LMU shared memory
       │
       ▼
race-core (Python)
  • TelemetryReader + StrategyService
  • UN loop global 20 Hz: spotter + CrewChiefEventSuite
  • Emite VoiceEvent → voice-brain
  • WS/UI: telemetría ~10 Hz, config, health

       │ VoiceEvent (JSON, localhost WS/TCP)
       ▼
voice-brain (Python, proceso separado)
  • Cola priorizada (IMMEDIATE > NORMAL), TTL estilo PlaybackModerator CC
  • Edge TTS + sounddevice (único reproductor de audio)
  • Whisper PTT + LLM
  • Ducking juego vía invoke Tauri (WASAPI)

       ▼
Tauri + React (solo UI)
  • Sin GET /tts en path crítico
  • PTT: graba WAV → POST
  • Mute global / subtítulos

supervisor.ps1: reinicia voice-brain si cae
```

## Contrato VoiceEvent (mínimo)

```json
{
  "id": "uuid",
  "ts": 1717777777.123,
  "text": "Coche a la izquierda",
  "priority": "IMMEDIATE",
  "category": "spotter",
  "channel": "spotter",
  "ttl_ms": 2000,
  "play_even_in_hard_parts": false
}
```

## Invariantes propuestos

1. Un snapshot por tick (`StrategyService.snapshot_frame()`)
2. Un evaluador global (nunca por conexión WS)
3. Un reproductor de audio (voice-brain, no React)
4. Slow path (LLM/TTS/Whisper) nunca en race-core
5. Release slim: Edge TTS only; ChromaDB/MQTT/traces off

## Alternativas ya descartadas por el equipo (cuestiona si procede)

- A. Monolito actual “arreglado con parches”
- C. CrewChief headless como motor de carrera
- D. Reescribir race-core en Rust/C#
- E. 3+ procesos (telemetry / race / voice / UI)

## Plan de migración (fases)

**Fase 0 (1–2 d):** `race_tick_loop` global 20 Hz; sacar CC de `telemetry_sender_loop`; tests sin WS conectado.

**Fase 1 (3–5 d):** `voice/service.py` in-process; backend reproduce audio; flag `VOICE_BACKEND_PLAYBACK=1`; frontend deja de hacer TTS para alertas.

**Fase 2 (5–7 d):** Split `race_core_main.py` + `voice_brain_main.py`; IPC localhost; supervisor; Tauri spawnea ambos.

**Fase 3 (3–4 d):** Eliminar duplicados (CommentaryOrchestrator off, 1 TTS, sin SpeechRecognition web); slim release; doctor.ps1.

**Fase 4 (continuo):** Smoke LMU 30 min, criterios V1–V6, p95 latencia spotter <500 ms.

## Criterios de aceptación (V1–V6)

| ID | Criterio |
|----|----------|
| V1 | Spotter audible con UI cerrada |
| V2 | CC suite corre sin WebSocket |
| V3 | Crash voice-brain → race-core sigue |
| V4 | N clientes WS no duplican eval CC |
| V5 | PTT no bloquea spotter >500 ms |
| V6 | Deploy verificable <2 min (doctor.ps1) |

---

# Tu tarea

Analiza la propuesta ADR-004 y el plan por fases. Responde **exactamente** con esta estructura:

## 1. Veredicto ejecutivo
- **Recomendación:** Aprobar / Aprobar con cambios / Rechazar / Alternativa preferida
- **Confianza:** Baja / Media / Alta
- **Una frase:** por qué

## 2. ¿Es la mayor simplificación posible con máxima fiabilidad?
- Respuesta sí/no/parcial con argumentos
- Qué simplificarías más
- Qué fiabilidad sacrificarías al simplificar más

## 3. Fallos y riesgos (mínimo 5)
Para cada uno: severidad (P0/P1/P2), probabilidad, mitigación concreta

## 4. Alternativa que propondrías
Diagrama ASCII breve + por qué es mejor/peor que ADR-004 **dado nuestro contexto** (paridad CC nativa, no usar CC, Windows, plazo corto)

## 5. Revisión por fase
Para Fase 0, 1, 2, 3, 4:
- **Viable:** Sí/No/Parcial
- **Estimación realista** (días-persona)
- **Dependencias omitidas**
- **Cambios que harías** (máx. 3 bullets)
- **Criterio de go/no-go** antes de pasar a la siguiente fase

## 6. Paridad CrewChief nativa
- ¿Este plan ayuda o perjudica la paridad?
- Módulos o comportamientos CC que quedarían mal ubicados
- ¿PlaybackModerator en voice-brain es correcto?

## 7. Preguntas bloqueantes
Lista preguntas que el equipo debe responder antes de implementar (máx. 7)

## 8. Puntuación (1–10)
| Dimensión | Nota | Comentario breve |
|-----------|------|------------------|
| Fiabilidad | | |
| Simplicidad | | |
| Time-to-market | | |
| Paridad CC | | |
| Mantenibilidad | | |
| Testabilidad | | |
| Operabilidad (deploy/debug) | | |

**Importante:** Si propones otra arquitectura, debe cumplir: paridad CC nativa sin ejecutar CrewChief, Windows LMU, LLM/PTT, estabilidad en pista.
```

---

## Variante — Solo Fase 0

Añade al final del prompt maestro:

```markdown
# Enfoque acotado

Analiza **solo la Fase 0** (race_tick_loop global, sacar CC del WebSocket, throttle UI 10 Hz).

Profundiza en:
- ¿Es suficiente para ship antes de voice-brain?
- Riesgos de regresión en spotter vs CC al unificar loops
- Diseño exacto de `race_tick_loop` (orden: strategy snapshot → spotter → CC on_frame → emit)
- Tests mínimos obligatorios

Ignora Fases 1–3 salvo dependencias directas con Fase 0.

En la sección 5, solo detalla Fase 0 con máximo detalle; resume 1–2 líneas el resto.
```

---

## Variante — Solo Fase 1 (voice in-process)

```markdown
# Enfoque acotado

Analiza **solo la Fase 1** (voice-brain in-process, sounddevice, flag VOICE_BACKEND_PLAYBACK).

Profundiza en:
- sounddevice vs alternativas Windows (NAudio, pygame, playsound, subprocess ffplay)
- Convivencia temporal frontend TTS + backend playback (doble audio)
- Cola IMMEDIATE vs NORMAL + preemption spotter sobre ingeniero
- Latencia alerta → oído realista con Edge TTS

Asume Fase 0 ya hecha.

Evalúa si Fase 1 sola resuelve el 80% del dolor de producción sin Fase 2.
```

---

## Variante — Solo Fase 2 (split procesos + IPC)

```markdown
# Enfoque acotado

Analiza **solo la Fase 2** (race_core_main + voice_brain_main + IPC + supervisor).

Profundiza en:
- WS vs TCP vs gRPC vs named pipe para VoiceEvent en localhost Windows
- Qué pasa si voice-brain está caído 30 s mid-race (cola, drop, buffer?)
- Split de routers FastAPI: qué API debe quedarse en race-core para PTT/UI
- Supervisor: script PS vs servicio Windows vs Tauri spawn

Asume Fases 0–1 hechas.

¿Fase 2 es prematura? ¿Qué evidencia exigirías antes de separar procesos?
```

---

## Variante — Solo Fase 3 (slim release)

```markdown
# Enfoque acotado

Analiza **solo la Fase 3** (eliminar duplicados, 1 TTS, python-embed vs PyInstaller).

Profundiza en:
- Orden seguro para retirar frontend TTS sin romper dev
- Impacto en tests existentes (`verify_voice_contract`, Vitest)
- PyInstaller vs python-embed vs cx_Freeze para 2 exes Python + deps Edge/Whisper
- Qué features DEBUG_FEATURES debe incluir sin sorpresas en beta

¿Qué eliminarías antes vs después de Fase 2?
```

---

## Variante — Devil's advocate (rechazar ADR)

```markdown
# Rol adicional

Asume la postura de **rechazar ADR-004** y defender la mejor alternativa posible dentro de nuestras restricciones.

Compara:
1. Monolito Python con audio 100% backend pero **un solo proceso** (sin split Fase 2)
2. Monolito + Rust solo para playback/ducking (Tauri sidecar mínimo)
3. Adiar voice-brain; solo Fase 0 + parches frontend hasta beta

Demuestra con modos de fallo concretos por qué dual-process **empeora** el sistema para un equipo pequeño.

Si aun así ADR-004 gana, dilo explícitamente.
```

---

## Cómo usar los resultados

1. Pega el **prompt maestro** en ≥3 modelos distintos.
2. Pega **una variante de fase** en el mismo modelo o en otro.
3. Opcional: **devil's advocate** en un modelo que tienda a ser optimista.
4. Consolida en una tabla:

| Tema | Modelo A | Modelo B | Modelo C | Consenso |
|------|----------|----------|----------|----------|
| Veredicto ADR | | | | |
| Fase 0 ship solo? | | | | |
| IPC preferido (F2) | | | | |
| sounddevice OK? | | | | |
| Mayor riesgo | | | | |

5. Si ≥2 modelos marcan el mismo **P0** no cubierto en ADR → actualizar ADR-004 antes de implementar.

---

## Metadatos (rellenar al pegar)

- **Fecha revisión:**
- **Modelo:**
- **Variante usada:** Maestro / Fase 0 / Fase 1 / Fase 2 / Fase 3 / Devil's advocate
- **Versión ADR:** 2026-06-07 (ADR-004 Proposed)
