# Prompt — Diseño abierto de arquitectura (sin plan previo)

Usa este prompt cuando quieras **opiniones frescas** antes de cerrar decisiones.  
**No incluye** ADR, fases, race-core, voice-brain ni ninguna propuesta interna.

Copia el **Prompt maestro abierto** a distintos modelos. Opcional: añade una **variante de enfoque** al final.

---

## Prompt maestro abierto

```markdown
# Rol

Eres un arquitecto de software senior con experiencia en:
- aplicaciones desktop en Windows
- sistemas en tiempo real (20–60 Hz)
- audio en apps de sim-racing / voice assistants
- Python, Rust, C#, TypeScript
- productos pequeños que deben llegar a beta sin reescribir todo

Tu trabajo **no** es validar un plan existente. **Diseña desde cero** (o re-diseña) la arquitectura técnica que consideres óptima para este producto, dado el contexto. Sé concreto: diagramas, procesos, contratos, trade-offs. Si algo del stack actual no tiene sentido, dilo y propón reemplazo.

# Producto — Vantare Ingeniero IA

## Qué es

Aplicación **desktop** para **Le Mans Ultimate (LMU)** que funciona como **ingeniero de pista + spotter por voz** en **español**, con **conversación libre por PTT** (push-to-talk) usando LLM.

El piloto corre con el juego en Windows; la app lee telemetría en vivo y le habla: proximidad lateral, combustible, banderas, pits, rivales, estrategia, etc. También puede **preguntar** al ingeniero (“¿cuánta gasolina me queda?”, “¿quién va delante?”).

## Referencia de comportamiento (no es dependencia)

**CrewChiefV4** es el estándar de mercado (~10 años, C#, monolito Windows): spotter, 40+ módulos deterministas de carrera, cola de audio con prioridades, mensajes que expiran si llegan tarde, validación de relevancia justo antes de hablar, ducking del volumen del juego.

**Vantare NO puede usar CrewChief como runtime** (no embebido, no fork obligatorio). El objetivo es **comportamiento lo más similar posible**, implementado en nuestro código, más el diferencial propio (LLM, español, UI moderna).

## Usuario y prioridades de producto

1. **Estabilidad en pista** — si el spotter o el ingeniero fallan en carrera, el producto no sirve
2. **Lanzar beta estable pronto** — equipo pequeño, ~1 año de desarrollo
3. **Paridad funcional CC en LMU** (determinista) + **PTT/LLM** (conversacional)
4. Calidad de voz aceptable en español (hoy TTS cloud/local; no voces humanas grabadas como CC)

## Stack actual (realidad del repo, no prescripción)

| Capa | Tecnología | Qué hace hoy |
|------|------------|--------------|
| Shell desktop | Tauri 2 + Rust (~220 líneas útiles) | Ventana overlay, tray, hotkeys PTT, spawn backend, ducking WASAPI vía invoke |
| UI | React 19 + TypeScript + Zustand | Dashboard, config, WebSocket telemetría, **cola de audio**, SpeechRecognition web, fetch TTS |
| Backend | Python 3.12 + FastAPI (~129 .py) | API REST, WebSocket, orquestación |
| Telemetría | C++/Python shared memory (`pyLMUSharedMemory`) @ ~20 Hz | Lectura in-process en Windows |
| Estrategia | `shared-strategy/` + `StrategyService` | Fuel, gaps, competidores, snapshots |
| Spotter | Python @ 20 Hz | Proximidad lateral, multiclase, geometría |
| Eventos CC | `crewchief_events/` ~25 módulos Python | Flags, fuel, penalties, rain, pits, multiclass, pearls, etc. |
| IA | LLM API, triggers, preemption, RAG/ChromaDB opcional | PTT respuestas, comentarios |
| Voz | Edge TTS (+ Piper/Eleven/Gemini en dev) | Síntesis en backend; **reproducción en frontend** (HTMLAudioElement) |
| ASR | Web Speech API + Whisper (backend) | PTT |
| Tests | Pytest (~110+), Vitest (~60+) | Contratos voz, spotter, CC modules |
| Deploy | PyInstaller (`backend.exe`) + Tauri installer | Windows; dev manual con scripts |

## Flujo actual simplificado (as-is)

```
LMU (shared memory)
    → Python TelemetryReader + StrategyService
    → Spotter (loop global ~20 Hz)
    → CrewChief modules (evalúan en path acoplado al WebSocket UI)
    → Alertas/eventos por WebSocket a React
    → React: gates, cola prioridad, GET /tts, reproduce audio
    → PTT: mic en navegador → pregunta → LLM stream → TTS → audio
```

## Diferencial vs CrewChief

| Vantare | CrewChief |
|---------|-----------|
| LLM conversacional libre (español) | 100% determinista, grammar commands |
| RAG / memoria eventos (opcional) | No |
| TTS sintético multi-backend | Voces grabadas + Windows TTS |
| UI web moderna (Tauri/React) | WinForms monolito |
| 1 juego (LMU) | 22+ juegos |

## Problemas observados (síntomas, sin diagnóstico impuesto)

- Spotter **detectado en logs backend** pero **inaudible** en app instalada
- Config UI y backend **desincronizados** (toggles spotter/ingeniero)
- Bugs en pipeline audio frontend → **silencio total** TTS
- Deploy PyInstaller **frágil** (copias parciales rompen instalación)
- Lógica de carrera y spotter **no siempre en el mismo ciclo** de evaluación
- Eventos CC parecen depender de **cliente WebSocket conectado**
- LLM/TTS y telemetría **comparten** runtime Python + event loop
- Latencia spotter con TTS cloud posiblemente alta para utilidad real

## Restricciones del equipo

- **No** usar CrewChiefV4 como binario/runtime
- **Sí** reutilizar lógica CC ya portada a Python donde tenga sentido
- **Windows first** (LMU shared memory nativa)
- **Mantener** LLM/PTT como feature core
- Equipo pequeño → evitar arquitecturas que multipliquen operación sin ROI claro
- Preferir **semanas a beta**, no reescritura total en otro lenguaje (salvo que argumentes fuerte)

## Lo que NO te damos

- Ningún ADR, plan de fases, ni arquitectura propuesta interna
- No asumas dual-process, monolito, microservicios, ni ningún patrón — **elige tú**

---

# Preguntas abiertas (responde todas)

## A. Arquitectura general

1. **¿Cómo diseñarías la arquitectura técnica completa?** (procesos, lenguajes, capas, diagrama ASCII o mermaid)
2. ¿Cuántos procesos/runtime en producción y por qué?
3. ¿Qué responsabilidades tendría el frontend vs el backend vs el shell Tauri/Rust?
4. ¿Monolito, multi-proceso, multi-hilo, o híbrido? Argumenta para **este** producto concreto.
5. ¿Qué eliminarías del stack actual en el primer corte hacia beta?

## B. Tiempo real y telemetría

6. ¿Cómo estructurarías el loop de juego a 20 Hz (telemetría → spotter → eventos CC)?
7. ¿Un snapshot por tick o múltiples lecturas? ¿Quién consume qué?
8. ¿Cómo evitarías que la UI (WebSocket) contamine la lógica de carrera?
9. ¿Python es adecuado para el hot path o moverías algo a Rust/C#? ¿Qué y cuánto?

## C. Audio y voz

10. **¿Dónde viviría la reproducción de audio?** (frontend, backend, OS nativo, otro)
11. ¿Cómo modelarías la cola de voz (prioridades spotter vs ingeniero vs LLM)?
12. ¿TTS cloud (Edge) vs local (Piper) vs pre-grabado para spotter? ¿Estrategia híbrida?
13. ¿Cómo implementarías ducking del juego de forma fiable en Windows?
14. ¿Dónde evaluarías “¿este mensaje sigue siendo válido?” antes de hablar (paridad CC)?
15. ¿PTT: captura en UI, backend, o ambos? ¿Streaming o batch?

## D. IA / LLM

16. ¿Dónde viviría el LLM respecto al motor de telemetría?
17. ¿Cómo aislarías latencia LLM del spotter sin over-engineering?
18. ¿RAG/ChromaDB en beta o post-beta? ¿Por qué?
19. ¿Qué parte del comentario proactivo sería determinista (CC) vs LLM?

## E. Paridad CrewChief nativa

20. ¿Cómo organizarías los ~25 módulos de eventos para mantener paridad sin duplicar lógica?
21. ¿Un solo “cerebro” de carrera o varios pipelines paralelos?
22. ¿Qué features CC **no** intentarías en beta?

## F. Frontend / shell

23. ¿Tauri sigue siendo el shell correcto vs Electron vs Qt vs otro?
24. ¿Qué debe hacer React en runtime de carrera vs solo en garaje/config?
25. ¿Overlay in-game necesario para beta?

## G. Deploy, ops, debug

26. **¿Cómo empaquetarías y desplegarías** en Windows de forma confiable?
27. ¿PyInstaller, python-embed, MSI, otro?
28. ¿Cómo debuggearías “no se oye nada” en máquina de un usuario?
29. ¿Qué health checks / doctor script incluirías?

## H. Testing y calidad

30. ¿Qué tests son imprescindibles antes de beta en pista?
31. ¿Cómo testearías audio end-to-end sin LMU corriendo?
32. ¿Contrato de voz: qué invariantes fijarías?

## I. Roadmap

33. Orden de implementación que **tú** elegirías (no más de 6 hitos)
34. ¿Qué shippearías en beta mínima vs v1.0?
35. Señales de que la arquitectura elegida **falló** y hay que pivotar

---

# Formato de respuesta

## 1. Visión en una página
Diagrama + 5 bullets de principios de diseño

## 2. Arquitectura propuesta
Detalle por capa (telemetría, eventos, audio, IA, UI, deploy)

## 3. Decisiones clave (tabla)
| Decisión | Opción elegida | Alternativa descartada | Por qué |

## 4. Riesgos top 5
P0/P1, mitigación

## 5. Respuestas numeradas
Responde las preguntas A1–I35 (puedes agrupar las similares; no omitas C10, C14, G26, A1)

## 6. Beta mínima
Qué incluir / excluir en primera beta estable

## 7. Preguntas que harías al equipo
Antes de escribir código (máx. 10)

## 8. Puntuación de confianza
¿Qué tan seguro estás de tu propuesta? (1–10) ¿Qué información te falta?

---

# Reglas

- No digas “depende” sin concretar bajo qué condiciones elegirías A vs B
- Si propones multi-proceso, justifica el coste operativo para un equipo pequeño
- Si propones monolito, explica cómo aislas LLM/audio del loop 20 Hz
- Cita patrones de CrewChief solo como **referencia de comportamiento**, no como “usa CC”
- Asume máquina típica del usuario: Windows 10/11, 8–16 GB RAM, LMU + app + posible VR
```

---

## Variante — Solo audio y voz (C + fragmento G)

Añade al final del prompt maestro:

```markdown
# Enfoque acotado

Responde con **máxima profundidad** las secciones C (audio) y G26–G28 (deploy/debug audio).
El resto (A, B, D…) resúmelo en ≤10 líneas cada bloque.
Prioriza latencia spotter y fiabilidad “siempre se oye”.
```

---

## Variante — Solo arquitectura de procesos (A + B)

```markdown
# Enfoque acutado

Profundiza en A1–A5 y B6–B9: procesos, loops, Python vs Rust.
Audio e IA solo a nivel de “quién vive dónde”, sin detalle TTS.
Incluye diagrama de secuencia para un tick de 20 Hz y para un PTT.
```

---

## Variante — Greenfield radical

```markdown
# Enfoque acutado

Ignora el stack actual salvo telemetría LMU (shared memory) y restricción “no CC runtime”.
Si empezaras el repo hoy desde cero, ¿qué stack elegirías?
Compara 2 opciones (ej. Python+Tauri vs C# monolito vs Rust core + web UI).
Elige una ganadora para beta en 8 semanas con 1–2 devs.
```

---

## Variante — Solo deploy y ops (G + H)

```markdown
# Enfoque acutado

Profundiza G26–G29 y H30–H32.
Asume que la lógica de carrera ya funciona en dev pero la app instalada falla intermitentemente.
¿Cómo empaquetar, verificar releases y soportar usuarios?
```

---

## Variante — Contrarian / anti-complejidad

```markdown
# Rol adicional

Propón la arquitectura **más simple posible** que aún cumpla:
- spotter audible en pista
- ingeniero PTT básico
- paridad CC “suficiente” en LMU (no 100%)

Cuenta líneas de infraestructura aproximadas. Ataca cualquier diseño que requiera >2 procesos o IPC de red.
```

---

## Cómo usar vs el prompt ADR

| Objetivo | Prompt |
|----------|--------|
| Opinión fresca, diseño desde cero | **Este doc — maestro abierto** |
| Validar plan interno ADR-004-R1 | `prompt-multi-model-adr-review.md` |
| Comparar modelos | Mismo prompt abierto a ≥3 modelos → tabla consenso |
| Evitar sesgo | **No** adjuntar ADR, checklist ni síntesis multi-modelo al pegar |

---

## Tabla de consolidación (plantilla)

| Tema | Modelo A | Modelo B | Modelo C | Consenso |
|------|----------|----------|----------|----------|
| Nº procesos runtime | | | | |
| Dónde reproduce audio | | | | |
| Dónde vive LLM | | | | |
| Loop 20 Hz — diseño | | | | |
| Empaquetado Windows | | | | |
| Shell (Tauri/Electron/otro) | | | | |
| Beta mínima (scope) | | | | |
| Mayor riesgo ignorado | | | | |

---

## Metadatos (rellenar al pegar)

- **Fecha:**
- **Modelo:**
- **Variante:** Maestro / Audio / Procesos / Greenfield / Deploy / Contrarian
- **¿Recibió plan interno?** Debe ser **No**
