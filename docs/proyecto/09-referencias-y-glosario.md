# 09 — Referencias y glosario

---

## ADRs (Architecture Decision Records)

Índice: [`../decisions/README.md`](../decisions/README.md)

| ADR | Tema |
|-----|------|
| ADR-001 | Electron como shell desktop |
| ADR-002 | GitHub Releases + auto-update |
| ADR-003 | Telemetría nativa Windows (mmap) |
| ADR-004 | Arquitectura voz — monolito backend (R1) |

Re-arquitectura Voice Beta: [`../architecture/2026-06-07-rearchitecture-decisions-record.md`](../architecture/2026-06-07-rearchitecture-decisions-record.md).

---

## Planes de ejecución (superpowers)

Carpeta: [`../superpowers/plans/`](../superpowers/plans/)

| Tipo | Patrón nombre |
|------|---------------|
| Roadmap versión | `2026-06-11-roadmap-vXX-*.md` |
| Executor completado | `2026-06-11-vXX-*-EXECUTOR.md` |
| Voice beta hitos | `2026-06-07-voice-beta-hito-*.md` |
| CrewChief port | `2026-06-07-crewchief-*.md` |
| Prompts agente | [`../superpowers/plans/prompts/`](../superpowers/plans/prompts/) |

---

## Documentación operativa

| Doc | Uso |
|-----|-----|
| [`../instalacion-desktop.md`](../instalacion-desktop.md) | Usuario final |
| [`../qa/electron-smoke-checklist.md`](../qa/electron-smoke-checklist.md) | QA post-release |
| [`../launch/release-process.md`](../launch/release-process.md) | Maintainer releases |
| [`../../CHANGELOG.md`](../../CHANGELOG.md) | Historial versiones |
| [`../../AGENTS.md`](../../AGENTS.md) | Guía agente (legacy parcial) |

---

## Evidencia y benchmarks

| Path | Contenido |
|------|-----------|
| `.omo/evidence/` | Validaciones LMU, matrices paridad CC, QA waves |
| `.omo/plans/` | Planes internos OMO |
| `docs/benchmark-llm.md` | Benchmarks LLM |

---

## Glosario

| Término | Significado |
|---------|-------------|
| **CC** | CrewChief — app referencia .NET |
| **LMU** | Le Mans Ultimate |
| **PTT** | Push-to-talk — tecla para hablar con ingeniero |
| **Spotter** | Alertas proximidad (left/right/clear) |
| **Pearl** | Perla de sabiduría — comentario ocasional motivacional |
| **Voice Beta** | Re-arquitectura v0.2.14 — audio en backend |
| **Hub** | Ventana Electron de configuración |
| **Overlay** | Ventana radio F1-style (speaking/listening) |
| **PhrasePicker** | Selector variantes frases por perfil |
| **PhraseStore** | Persistencia overrides frases AppData |
| **PersonalityPack** | Perfil tono + runtime sweary/proactivity/pearls |
| **GATE** | Checklist cierre versión antes de tag |
| **Mini-plan** | Plan TDD task-by-task por versión roadmap |
| **Invariante I1–I5** | Reglas contrato voz no negociables |
| **Monolito** | Un solo `backend.exe` con todo el runtime carrera |
| **REST PitMenu** | API LMU puerto 6397 para menú boxes |
| **NSIS** | Instalador Windows electron-builder |
| **AppData** | `%APPDATA%/Vantare/` datos usuario |

---

## Enlaces externos

- Repo: https://github.com/isaacalbala12/Vantare-Ingeniero
- Releases: https://github.com/isaacalbala12/Vantare-Ingeniero/releases
- CrewChief V4: https://github.com/Spriggans12/CrewChiefV4
- LMU shared memory: via `pyLMUSharedMemory` en shared-telemetry

---

## Contacto / issues

Bugs y features: GitHub Issues del repositorio.

Al reportar bugs de voz incluir: versión app, circuito, modo sesión, toggles Hub (engineer/spotter/speak-only), log backend si posible.
