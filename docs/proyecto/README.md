# Documentación del proyecto — Vantare Ingeniero IA

> **Carpeta canónica** para entender qué es el producto, cómo está construido, dónde vamos y cómo continuar el trabajo con agentes IA.
>
> **Versión de referencia:** v0.5.1 (junio 2026)  
> **Repositorio:** [isaacalbala12/Vantare-Ingeniero](https://github.com/isaacalbala12/Vantare-Ingeniero)

---

## Para empezar

| Si quieres… | Lee |
|-------------|-----|
| Entender el producto y la visión | [01-vision-y-producto.md](01-vision-y-producto.md) |
| Ver cómo está montado el código hoy | [02-arquitectura-tecnica.md](02-arquitectura-tecnica.md) |
| Saber qué ya está hecho (0.2→0.5) | [03-estado-actual.md](03-estado-actual.md) |
| Plan futuro 0.6→1.1 | [04-roadmap-futuro.md](04-roadmap-futuro.md) |
| Backend: módulos y carpetas | [05-modulos-backend.md](05-modulos-backend.md) |
| Frontend: Hub, overlay, config | [06-frontend-hub-overlay.md](06-frontend-hub-overlay.md) |
| Voz, spotter, CrewChief parity | [07-voz-spotter-crewchief.md](07-voz-spotter-crewchief.md) |
| Dev, tests, build, releases | [08-desarrollo-y-release.md](08-desarrollo-y-release.md) |
| ADRs, glosario, referencias | [09-referencias-y-glosario.md](09-referencias-y-glosario.md) |
| **Continuar en otra sesión (orquestador)** | [ORQUESTADOR-PROMPT-CONTINUACION.md](ORQUESTADOR-PROMPT-CONTINUACION.md) |

---

## Mapa del repositorio (alto nivel)

```
Vantare-Ingeniero/
├── backend/              # FastAPI + inteligencia + voz + CC events (monolito Python)
├── frontend/             # Electron + React Hub + overlay F1-style
├── shared-telemetry/     # Lectura LMU shared memory (Python; Rust en 1.1)
├── shared-strategy/      # Estrategia determinista (fuel, tyres, pits)
├── native/duck_lmu/      # Ducking audio LMU (Rust, opcional en bundle)
├── scripts/              # build-desktop, verify_*, doctor
├── docs/
│   ├── proyecto/         # ← ESTA CARPETA (handbook del producto)
│   ├── superpowers/plans/  # Mini-planes TDD por versión (ejecución agentes)
│   ├── architecture/     # ADRs, pipelines CC, decisiones re-arquitectura
│   ├── voice-contract.md # Contrato normativo voz (tests + invariantes I1–I5)
│   └── ROADMAP-1.0.md    # Visión producto 0.3→1.1
└── CHANGELOG.md          # Historial de releases
```

---

## Documentos externos importantes (no duplicados aquí)

Estos siguen siendo **source of truth** para su dominio; la carpeta `proyecto/` los resume y enlaza:

| Documento | Rol |
|-----------|-----|
| [`../ROADMAP-1.0.md`](../ROADMAP-1.0.md) | Visión producto y criterios "done" por versión |
| [`../superpowers/plans/2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](../superpowers/plans/2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md) | Índice orquestador + gates + forbidden global |
| [`../superpowers/plans/2026-06-11-roadmap-1.0-master-plan.md`](../superpowers/plans/2026-06-11-roadmap-1.0-master-plan.md) | Plan maestro + mapa de archivos |
| [`../voice-contract.md`](../voice-contract.md) | Qué debe oírse / silenciarse (tests) |
| [`../crewchief-comparison.md`](../crewchief-comparison.md) | Matriz paridad feature vs CrewChief |
| [`../decisions/README.md`](../decisions/README.md) | ADRs (Electron, auto-update, telemetría nativa) |
| [`../../CHANGELOG.md`](../../CHANGELOG.md) | Detalle de cada release |
| [`../../AGENTS.md`](../../AGENTS.md) | Guía rápida para agentes (parcialmente desactualizada → preferir esta carpeta) |

---

## Regla de oro del roadmap

> **Un cerebro de voz por app. Monolito `backend.exe` en LMU hasta 1.0. iRacing + Suite Go solo en 1.1.**

No abrir scope de iRacing, overlays telemetría in-game, ni launcher Suite hasta cerrar **0.9** (hardening LMU) y **1.0** (clonación voz).

---

## Mantenimiento de esta carpeta

Actualizar **`03-estado-actual.md`** y la tabla de gates en el prompt de orquestación tras cada release. Los mini-planes en `docs/superpowers/plans/` son la fuente de ejecución task-by-task; este handbook es la **narrativa consolidada**.
