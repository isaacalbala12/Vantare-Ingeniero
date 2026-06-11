# v0.7 — Comandos ingeniero (consultas CC) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PTT/consultas estilo CrewChief con **datos deterministas** (fuel, damage, tyres, gaps, session, opponents) — LLM solo redacta, nunca inventa cifras.

**Architecture:** Extender `pilot_tool_executor.py` con tools P0; cada tool devuelve `StructuredFact` → `pilot_ptt_agent` prompt con facts-only; matriz tests en `voice-contract` + `test_engineer_commands.py`.

**Tech Stack:** Python 3.12, LLM tools StepFun/OpenAI-compatible, pytest.

**Orquestador:** [`2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md)

**Referencia CC:** [`../../crewchief-comparison.md`](../../crewchief-comparison.md) § consultas fuel/tyres/damage

---

## Preconditions

- [ ] v0.6 GATE ✅
- [ ] `pilot_tool_executor.py` + `damage_report.py` existentes

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Modify | `backend/src/intelligence/pilot_tool_executor.py` |
| Modify | `backend/src/intelligence/pilot_ptt_agent.py` |
| Create | `backend/src/intelligence/tools/fuel_queries.py` |
| Create | `backend/src/intelligence/tools/tyre_queries.py` |
| Create | `backend/src/intelligence/tools/gap_queries.py` |
| Modify | `backend/src/intelligence/damage_report.py` |
| Modify | `docs/voice-contract.md` (§ PTT commands) |
| Create | `backend/tests/test_engineer_commands.py` |
| Create | `backend/tests/fixtures/engineer_command_matrix.py` |

---

## Task 1: Fuel queries tool

- [ ] **Step 1: Failing test**

```python
@pytest.mark.asyncio
async def test_fuel_for_laps_returns_litres_and_laps(engine_with_snapshot):
    result = await execute_tool(engine_with_snapshot, "fuel_for_laps", {"laps": 5})
    assert result.facts["laps"] == 5
    assert result.facts["litres_remaining"] > 0
    assert "estimate" in result.facts
```

- [ ] **Step 2: Implement `fuel_queries.py`** — usa `StrategyService`, `fuel_percentile.py`
- [ ] **Step 3: Register tool** in `pilot_tool_executor.py`
- [ ] **Step 4: Commit**

---

## Task 2: Tyre + damage queries

- [ ] Tools: `tyre_compound`, `tyre_age_laps`, `damage_summary`
- [ ] Tests with fixture snapshot from `tests/fixtures/`
- [ ] LLM prompt: `FACTS: {...}` block mandatory

---

## Task 3: Gap + session + opponents

- [ ] Tools: `gap_ahead`, `gap_behind`, `session_time_remaining`, `watched_opponent_behind`
- [ ] Wire `gaps.py`, `live_context.py`

---

## Task 4: Command matrix + voice-contract

- [ ] `engineer_command_matrix.py` — 1 row per command, expected tool name
- [ ] `scripts/verify_voice_contract.py` extend PTT section
- [ ] Update `docs/voice-contract.md`

---

## Task 5: GATE v0.7

- [ ] Bump 0.7.0
- [ ] `pytest tests/test_engineer_commands.py -v` all PASS
- [ ] Manual PTT: "¿cuánta gasolina para 10 vueltas?" → cifra coherente con HUD

---

## GATE v0.7

| Invariante | Verificación |
|------------|--------------|
| I1 LLM never returns number not in facts | test mocks LLM, assert prompt contains facts |
| I2 Unknown data → "no data" phrase | test empty snapshot |
| I3 PTT always passes voice-contract I2 | `verify_voice_contract.py` |
