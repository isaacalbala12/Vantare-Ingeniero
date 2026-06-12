# Roadmap 1.0 — Paridad CrewChief (arquitectura simple)

> **Estado:** Acordado — guía de producto  
> **Ejecución (planes TDD):** [`superpowers/plans/2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](superpowers/plans/2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md)  
> **Plan maestro:** [`superpowers/plans/2026-06-11-roadmap-1.0-master-plan.md`](superpowers/plans/2026-06-11-roadmap-1.0-master-plan.md)  
> **Base estable:** v0.2.14 (Voice Beta, LMU)  
> **Comparativa CC:** [`crewchief-comparison.md`](crewchief-comparison.md)  
> **Arquitectura voz (hecha):** [`architecture/2026-06-07-rearchitecture-decisions-record.md`](architecture/2026-06-07-rearchitecture-decisions-record.md)

---

## 1. Objetivo

**Imitar y superar CrewChief** en lo que importa para endurance en sim — voz, spotter, ingeniero, boxes — empezando por **LMU**, con **iRacing** en 1.1.

**Prioridades (orden fijo):**

1. Estabilidad en pista (audible, predecible, sin sorpresas de instalador)
2. Calidad humana (frases, personalidad, idioma)
3. Capacidad CC (consultas, pit por voz)
4. Identidad vocal (clonación)
5. Plataforma dual-app + segundo sim (solo cuando 0.9–1.0 estén sólidos)

---

## 2. Principio rector — lo más simple posible

> **Un cerebro de voz por app. Telemetría compartida solo en librería, no en runtime obligatorio. Dos productos independientes; integración opcional en 1.1.**

| Regla | Significado |
|-------|-------------|
| **Monolito Vantare** | `backend.exe` = telemetría + spotter + CC + voz + LLM. Sin microservicios locales. |
| **Go overlay aparte** | HUD/visual en Go; **no** es dependencia de Vantare ni al revés. |
| **Sin overlays in-game en Vantare** | Otra app cubre telemetría visual; Vantare solo overlay de **radio** (speaking/listening). |
| **Complejidad en el límite de versión** | Suite, bus MQTT, iRacing → **1.1**, no antes. |
| **Segmentar solo con métricas** | Segundo proceso / IPC solo si GIL o latencia lo exigen en pista. |

**No es:** dos CrewChief compitiendo por mmap, launcher obligatorio, big-bang iRacing.  
**Es:** Vantare excelente solo en LMU → voz clonada → ampliar sim + convivencia opcional con Go.

---

## 3. Mapa de versiones

| Versión | Eje | Paridad CC (resumen) |
|---------|-----|----------------------|
| **0.2.14** ✅ | Voice Beta stable | Audio backend, race loop, overlay radio WS |
| **0.3** | Copy + TTS | Frases humanas, Gemini voz premium |
| **0.4** | Customización | Frases de triggers editables (export/import) |
| **0.5** | Personalidad | Perfiles avanzados, sweary, verbosidad, mood |
| **0.6** | Idioma | Inglés en toda la app (UI Hub/overlay + frases + TTS + NumberProcessing) |
| **0.7** | Ingeniero consultable | Fuel, daños, neumáticos, gaps, tiempos, oponentes |
| **0.8** | Pit Manager LMU | REST write: fuel, tyres, repairs, energy (confirmación voz) |
| **0.9** | Ship quality LMU | Hardening + validación multi-circuito |
| **1.0** | Identidad vocal | Clonación básica por perfil |
| **1.1** | iRacing + Suite | Mapper iRacing + apps independientes integrables |

---

## 4. Arquitectura por era

### 4.1 Era 0.3–0.9 — solo Vantare, solo LMU

Sin cambiar el monolito acordado en ADR-004-R1:

```
LMU shared memory
       │
       ▼
┌─────────────────────────────────────────┐
│ backend.exe                              │
│  race_loop @ 20 Hz (global)               │
│  voice_loop (pygame, cola, moderador)      │
│  crewchief_events + spotter + LLM PTT      │
│  FastAPI /ws + /health                     │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│ Electron Hub + overlay radio (UI pasiva voz) │
└─────────────────────────────────────────────┘
```

**Invariantes (siguen vigentes):** un snapshot/tick, un evaluador global, audio solo backend, un `backend.exe` por sesión.

**Fuera de scope 0.3–0.9:**

- Overlays telemetría in-game en Vantare
- Launcher Suite / Go integration
- iRacing
- SDK público, CoDriver rally

---

### 4.2 Era 1.0 — clonación voz (monolito intacto)

Mismo diagrama 4.1 + capa TTS:

- Perfil → timbre clonado (fallback Gemini/Edge)
- Consentimiento + muestra mínima de audio
- Sin segundo exe ni bus nuevo

---

### 4.3 Era 1.1 — iRacing + Suite (simplest dual-app)

**Problema:** Go (overlay) y Vantare (voz) deben funcionar **por separado** y **juntos** sin duplicar reglas de negocio ni parsers dos veces en Python y Go.

**Solución mínima:**

```
                    ┌─── Vantare solo ───┐
                    │ backend.exe         │
LMU / iRacing ──────┤ shared-telemetry    │──► voz + spotter + ingeniero
                    │ (Rust, una vez)     │
                    └─── Go solo ─────────┘
                         Go + shared-telemetry (CGO) ──► HUD

Opcional (Suite):
  vantare-suite.exe → arranca 1..N apps, config compartida, sin acoplar runtime
  bus localhost (MQTT/WS) → solo si ambas apps detectan peer
```

| Modo | Vantare | Go overlay | Launcher |
|------|---------|------------|----------|
| `vantare-only` | ✅ | — | — |
| `overlay-only` | — | ✅ | — |
| `suite` | ✅ | ✅ | opcional |

**Anti-duplicación (1.1):**

- **Un crate** `shared-telemetry`: LMU + iRacing mappers, `TelemetryFrame` común
- **Reglas de carrera** (spotter, triggers, pit): solo en Vantare Python
- **Go:** render + layout; lee frame normalizado, no reimplementa CC
- **Bus opcional:** publicar/subscribir eventos (`telemetry_frame`, `voice_playback_*`) cuando conviene; ignorar si la otra app no está

**iRacing (fases 1.1, no big-bang):**

| Fase | Entregable |
|------|------------|
| 1.1a | Read iRSDK + session state |
| 1.1b | Spotter iRacing |
| 1.1c | Triggers endurance (flags, fuel, tyres, penalties) |
| 1.1d | Pit/comandos iRacing (donde API lo permita) |
| 1.1e | Selector sim + Suite launcher |

---

## 5. Criterios “done” por versión

### 0.3 — Frases + Gemini
- [ ] Catálogo triggers revisado (tono humano, variación, sin robótico)
- [ ] Gemini TTS selectable por perfil
- [ ] Tests contrato voz + spotter audio sin regresión

### 0.4 — Frases editables
- [ ] UI o JSON: editar/exportar/importar frases por trigger
- [ ] Defaults empaquetados; overrides en `%APPDATA%`
- [ ] Fallback a default si frase usuario vacía/inválida

### 0.5 — Personalidades
- [ ] `PersonalityPack` avanzado (sweary, verbosidad, proactividad, pearls)
- [ ] Sincronía config Hub ↔ backend (`config_ack`)

### 0.6 — Inglés
- [ ] `spotter_phrases_en.json` + triggers EN
- [ ] TTS EN por perfil
- [ ] Números/tiempos localizados (estilo CC NumberProcessing)
- [ ] Hub + overlay con textos principales localizados por `uiLanguage`
- [ ] Selector simple `uiLanguage` / `voiceLanguage` en configuración; onboarding queda para futuro

### 0.7 — Comandos ingeniero
- [ ] Tools deterministas: fuel, damage, tyres, gaps, session time, opponents
- [ ] PTT híbrido: tool → dato duro → LLM redacta (no inventar cifras)
- [ ] Matriz tests por comando (`voice-contract`)

### 0.8 — Pit Manager LMU
- [ ] Read plan + confirmación voz + execute REST LMU
- [ ] P0: fuel add/to-end, tyres all/front/rear, fix none/body/all
- [ ] LMU: virtual energy %, fuel ration %
- [ ] Guard: solo pit lane / menú válido

### 0.9 — Hardening LMU
- [ ] `verify-release.ps1` + `verify_beta_gate.ps1` green
- [ ] Auto-update end-to-end (CI → asset íntegro → Hub)
- [ ] `duck_lmu.exe` en bundle
- [ ] Checklist **≥3 circuitos × ≥2 condiciones** (evidencia en `.omo/evidence/`)
- [ ] **Sin** launcher, **sin** Go, **sin** iRacing

### 1.0 — Clonación voz
- [ ] 1 timbre clonado por perfil + fallback TTS
- [ ] Flujo consentimiento + muestra
- [ ] Release stable (no pre-release)

### 1.1 — iRacing + Suite
- [ ] `shared-telemetry` iRacing + frame unificado LMU/iRacing
- [ ] Vantare spotter + triggers iRacing (fases a–c mínimo)
- [ ] Go standalone con mismo crate (sin backend Python)
- [ ] Vantare standalone sin Go (LMU + iRacing)
- [ ] Launcher Suite **opcional** + Companion API v1 documentada
- [ ] Coexistencia: puertos, ducking único, detección peer

---

## 6. Retirado / prohibido (global)

- ❌ Overlays telemetría in-game en Vantare (gaps chart, tyre heat, VR)
- ❌ Launcher obligatorio para usar Vantare o Go
- ❌ Go dependiente de `backend.exe` para arrancar
- ❌ Segundo parser LMU/iRacing en Go sin pasar por `shared-telemetry`
- ❌ 2 exe + supervisor WS (descartado en ADR-004-R1)
- ❌ CrewChiefV4 como runtime

---

## 7. Relación con otros documentos

| Documento | Rol |
|-----------|-----|
| [`proyecto/README.md`](proyecto/README.md) | **Handbook consolidado** — visión, arquitectura, estado v0.5.1, prompt orquestador |
| [`superpowers/plans/2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](superpowers/plans/2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md) | **Orquestador** — mini-planes 0.3→1.1, gates, protocolo agente |
| [`superpowers/plans/prompts/2026-06-11-v03-EXECUTOR-PROMPT.md`](superpowers/plans/prompts/2026-06-11-v03-EXECUTOR-PROMPT.md) | **Prompt ejecutor v0.3** (copiar al implementador) |
| [`superpowers/plans/2026-06-11-roadmap-1.0-master-plan.md`](superpowers/plans/2026-06-11-roadmap-1.0-master-plan.md) | Plan maestro + mapa de archivos |
| [`ROADMAP-beta.md`](ROADMAP-beta.md) | Deuda alpha/beta histórica |
| [`crewchief-comparison.md`](crewchief-comparison.md) | Backlog paridad feature-por-feature |
| [`voice-contract.md`](voice-contract.md) | Contrato normativo voz (tests) |
| [`launch/release-process.md`](launch/release-process.md) | Tag, CI, smoke post-release |

---

## 8. Cronograma orientativo (no compromiso)

```
0.2.14 ──► 0.3 ──► 0.4 ──► 0.5 ──► 0.6 ──► 0.7 ──► 0.8 ──► 0.9 ──► 1.0 ──► 1.1
  stable     voz      UX       persona   EN      ask     pit     ship    clone   iR+Suite
```

**Regla de oro:** no abrir 1.1 hasta 0.9 validada en pista y 1.0 estable en TTS pipeline.
