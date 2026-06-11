# v0.5 — Personalidades avanzadas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Perfiles de personalidad **avanzados** (sweary, verbosidad, proactividad, pearls) sincronizados Hub ↔ backend, afectando prompts LLM y selección de frases.

**Architecture:** Extender `PersonalityPack` + `VerbosityController` + config WS; sin nuevo proceso. Personalidad = datos + reglas, no otro LLM.

**Tech Stack:** Python 3.12, React Hub, pytest, Vitest.

**Orquestador:** [`2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md)

---

## Preconditions

- [ ] v0.4 GATE ✅

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Modify | `backend/src/intelligence/personality_pack.py` |
| Modify | `backend/src/intelligence/verbosity_controller.py` |
| Modify | `backend/src/intelligence/pearls_of_wisdom.py` |
| Modify | `backend/src/intelligence/commentary_orchestrator.py` |
| Modify | `frontend/src/store/config.ts`, Hub Perfiles |
| Modify | `backend/tests/test_personality_pack.py`, `test_verbosity_controller.py` |

---

## Task 1: Modelo PersonalityProfile v2

- [ ] **Step 1: Failing test**

```python
def test_sweary_profile_injects_tone_suffix():
    pack = PersonalityPack(profile_id="aggressive", sweary=True)
    assert "lenguaje coloquial" in pack.engineer_system_suffix().lower() or pack.sweary_enabled
```

- [ ] **Step 2: Add fields:** `sweary: bool`, `verbosity: low|normal|high`, `proactivity: low|normal|high`, `pearl_frequency: float 0-1`

- [ ] **Step 3: Wire `VerbosityController`** — high → más commentary batch; low → solo IMMEDIATE + PTT.

- [ ] **Step 4: Commit**

---

## Task 2: Hub Perfiles UI

- [ ] Sliders/toggles: sweary, verbosidad, proactividad, pearls
- [ ] Preview texto tono ingeniero (static)
- [ ] `test_config_sync_ws.py` round-trip nuevos fields

---

## Task 3: Pearls + commentary gating

- [ ] `pearls_of_wisdom.py` usa `pearl_frequency` del perfil
- [ ] Test: frequency 0 → no pearls en 100 ticks simulados

---

## Task 4: Release v0.5 GATE

- [ ] Bump 0.5.0
- [ ] `verify_beta_gate.ps1` PASS
- [ ] Pista manual: cambiar perfil aggressive+sweary → tono audible distinto

---

## GATE v0.5

| Invariante | Test |
|------------|------|
| I1 config_ack incluye personality fields | `test_config_sync_ws` |
| I2 sweary off → sin muletillas en prompt | `test_personality_pack` |
| I3 verbosity low bloquea engineer proactivo | `test_verbosity_controller` |
