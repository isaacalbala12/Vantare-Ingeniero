# v1.1 — iRacing + Suite (apps independientes) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Segundo sim **iRacing** + plataforma **dual-app**: Vantare y overlay Go funcionan **por separado** o **juntas** vía `shared-telemetry` común y Suite launcher **opcional**.

**Architecture:** Extender crate `shared-telemetry` con mapper iRacing → `TelemetryFrame` unificado. Vantare: spotter + triggers iRacing en monolito Python. Go: CGO al mismo crate (standalone). Bus localhost + launcher solo en modo `suite` opt-in.

**Tech Stack:** Rust `shared-telemetry`, Python bindings, Go CGO, iRSDK, pytest, Go tests (repo externo).

**Orquestador:** [`2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md)

---

## Preconditions

- [ ] v1.0 GATE ✅
- [ ] Go overlay repo accessible to agent (separate clone)

---

## Modos de operación (invariantes)

| Modo | Vantare backend | Go overlay | Launcher |
|------|-----------------|------------|----------|
| `vantare-only` | ✅ | — | — |
| `overlay-only` | — | ✅ + shared-telemetry | — |
| `suite` | ✅ | ✅ | opcional |

| ID | Invariante |
|----|------------|
| I1 | Go **never** requires `backend.exe` to start |
| I2 | Vantare **never** requires Go to start |
| I3 | Parsers LMU/iRacing live **once** in `shared-telemetry` |
| I4 | Spotter/triggers/pit logic stay in Vantare Python only |
| I5 | Bus MQTT/WS is opt-in when peer detected |

---

## Fases 1.1 (orden fijo)

| Fase | Entregable | Mini-plan section |
|------|------------|-------------------|
| 1.1a | iRSDK read + TelemetryFrame | Task 1–2 |
| 1.1b | Spotter iRacing | Task 3 |
| 1.1c | Triggers endurance iRacing | Task 4 |
| 1.1d | Pit iRacing (si API) | Task 5 (optional) |
| 1.1e | Suite + Companion API v1 | Task 6–8 |

---

## Task 1: TelemetryFrame sim-agnostic

**Files:**
- Modify: `shared-strategy/src/shared_strategy/models.py` (if needed)
- Modify: `shared-telemetry/` — add `sim_id: lmu | iracing`

- [ ] **Step 1: Test** existing LMU frames unchanged
- [ ] **Step 2: Add `SimId` enum** — regression pytest native telemetry

---

## Task 2: iRacing mapper (1.1a)

**Files:**
- Create: `shared-telemetry/src/iracing/` (or project convention)
- Create: Python binding tests `backend/tests/test_iracing_telemetry_frame.py`

- [ ] **Step 1: Read iRSDK session** — position, lap, fuel, flags minimal
- [ ] **Step 2: Map to TelemetryFrame** — same fields LMU consumers use
- [ ] **Step 3: Config `SIMULATOR=iracing|lmu`** in backend `.env`

---

## Task 3: Spotter iRacing (1.1b)

**Files:**
- Create: `backend/src/intelligence/iracing_spotter_adapter.py`
- Reuse: `cartesian_spotter.py` geometry where applicable

- [ ] Tests with recorded iRacing frame fixtures JSON
- [ ] Voice path unchanged — same `voice_loop`

---

## Task 4: Triggers iRacing (1.1c)

- [ ] Enable `crewchief_events` modules that apply to iRacing data
- [ ] Skip LMU-only REST pit triggers when `sim_id != lmu`

---

## Task 5: Pit iRacing (1.1d, optional)

- [ ] Spike iRacing pit menu API availability
- [ ] If no stable write API → document defer; read-only plan summary only

---

## Task 6: Go shared-telemetry CGO (standalone)

**Files:** Go repo (external)

- [ ] **Step 1: CGO link** to `shared-telemetry` static lib
- [ ] **Step 2: Go reads iRacing/LMU** without Python
- [ ] **Step 3: Test** Go binary starts with sim running, no backend.exe

---

## Task 7: Companion API v1 (optional together)

**Files:**
- Create: `docs/companion-api-v1.md`
- Modify: `backend/src/routers/` or MQTT topics documented

Events:

```
telemetry_frame (20Hz)
voice_playback_start / voice_playback_end
session / strategy snapshot
health
```

- [ ] Go subscribes when env `VANTARE_COMPANION=1` and peer port open
- [ ] Vantare publishes only if `COMPANION_PUBLISH=1`

---

## Task 8: Suite launcher (optional)

**Files:**
- Create: `suite/` or separate repo `vantare-suite` (Go recommended)

- [ ] `vantare-suite.exe start --sim iracing --with-overlay`
- [ ] `vantare-suite.exe start --vantare-only`
- [ ] Coordinated quit; **not** in critical path of either app installer

---

## Task 9: GATE v1.1

- [ ] Bump 1.1.0
- [ ] LMU regression: `verify_beta_gate.ps1` PASS
- [ ] iRacing: spotter audible manual evidence
- [ ] Go standalone: starts without backend
- [ ] Vantare standalone: starts without Go
- [ ] Suite optional: both start + one telemetry publisher (config doc)

---

## GATE v1.1

| Check | Expected |
|-------|----------|
| I1–I5 invariants | tests + manual matrix |
| LMU unchanged | full gate PASS |
| iRacing read | fixture + live smoke |
| Companion doc | `docs/companion-api-v1.md` merged |
| No mandatory launcher | install Vantare alone works |

---

## Files FORBIDDEN (1.1)

- ❌ Telemetry overlays in Vantare Electron
- ❌ Duplicate iRacing parser in Go without shared-telemetry
- ❌ Mandatory Suite in NSIS installer
