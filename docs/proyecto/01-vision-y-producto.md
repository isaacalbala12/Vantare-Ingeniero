# 01 — Visión y producto

## Qué es Vantare Ingeniero IA

**Vantare Ingeniero IA** es una aplicación de escritorio para **Windows** que actúa como **ingeniero de pista y spotter por voz** mientras conduces en **Le Mans Ultimate (LMU)**.

No es un overlay de telemetría visual (gaps, neumáticos, gráficos). Es **radio de boxes**: alertas auditivas, spotter de proximidad, comentarios proactivos del ingeniero y conversación por **PTT** (push-to-talk) con un LLM que conoce el estado de la carrera.

### Propuesta de valor

| Para el piloto | Cómo lo entrega Vantare |
|----------------|-------------------------|
| Saber si hay coche a los lados / adelante / atrás | Spotter cartesiano ~20 Hz, frases naturales en español |
| Avisos de combustible, FCY, lluvia, desgaste, pits | Módulos estilo CrewChief (`crewchief_events/`) + triggers |
| Preguntar al ingeniero en voz | PTT → ASR → LLM con contexto de telemetría |
| Personalizar tono y frecuencia | Perfiles (formal/standard/aggressive), sweary, proactividad, perlas |
| Editar frases propias | Editor Hub + JSON en AppData |

### Referencia de mercado

El benchmark funcional es **[CrewChief](https://github.com/Spriggans12/CrewChiefV4)** (.NET, multi-sim). Vantare **no ejecuta CrewChief**; reimplementa la lógica relevante en Python nativo, con foco inicial en **LMU endurance** y **español** (inglés en v0.6).

Comparativa detallada: [`../crewchief-comparison.md`](../crewchief-comparison.md).

---

## Objetivo estratégico (roadmap 1.0)

**Imitar y superar CrewChief** en lo que importa para endurance en sim:

1. **Estabilidad en pista** — audible, predecible, instalador que funciona
2. **Calidad humana** — frases, personalidad, idioma
3. **Capacidad CC** — consultas al ingeniero, pit por voz
4. **Identidad vocal** — clonación de voz por perfil (v1.0)
5. **Plataforma dual-app** — iRacing + overlay Go opcional (v1.1)

Visión completa: [`../ROADMAP-1.0.md`](../ROADMAP-1.0.md).

---

## Principio rector de arquitectura

> **Un cerebro de voz por aplicación. Telemetría compartida solo como librería. Dos productos independientes (Vantare vs overlay Go); integración opcional en 1.1.**

| Decisión | Significado |
|----------|-------------|
| Monolito `backend.exe` | Telemetría + spotter + CrewChief events + TTS + LLM en **un proceso Python** |
| Electron = UI pasiva | Hub (config), overlay de **radio** (hablando/escuchando), auto-update |
| Audio en backend | Tras Voice Beta (v0.2.14): pygame reproduce en Python; frontend solo refleja estado WS |
| Sin HUD in-game en Vantare | Gaps chart, tyre heat, VR → **fuera de scope** (otra app Go en 1.1) |
| Sin iRacing hasta 1.1 | Solo LMU en 0.3–0.9 |

---

## Usuario objetivo

- Piloto de sim **endurance** en LMU (WEC, multiclass, carreras largas)
- Windows 10/11 x64, juego en borderless/windowed
- Dispuesto a configurar `LLM_API_KEY` (StepFun, OpenAI-compatible, etc.)
- Opcional: `GEMINI_API_KEY` para TTS premium por rol

---

## Canales de distribución

- **GitHub Releases** — instalador NSIS `vantare-ingeniero-X.Y.Z-setup.exe`
- **Auto-update** desde Hub → Avanzado (electron-updater + `latest.yml`)
- **Nota:** instaladores sin certificado Authenticode; SmartScreen puede avisar; desde v0.5.1 el updater no exige firma digital

Instalación: [`../instalacion-desktop.md`](../instalacion-desktop.md).

---

## Qué NO es (explícitamente fuera de scope hasta 1.1+)

- Overlay de telemetría visual in-game en Vantare
- Launcher obligatorio tipo "Suite" para usar la app
- iRacing, rFactor, Assetto Corsa (solo LMU hasta 0.9)
- Clonación de voz del piloto real (→ v1.0)
- SDK público estilo CrewChief para terceros
- CoDriver rally / pace notes
- Dependencia de CrewChiefV4 en runtime

Deuda diferida histórica: [`../ROADMAP-beta.md`](../ROADMAP-beta.md).

---

## Equipo y modo de trabajo

Desarrollo asistido por **agentes IA** (Cursor) con:

- **Orquestador** — elige versión, revisa gates, no implementa todo
- **Ejecutor** — implementa un mini-plan de `docs/superpowers/plans/` task-by-task
- **Gates** — pytest + vitest + smoke manual antes de tag release

Protocolo: [`../superpowers/plans/2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](../superpowers/plans/2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md).
