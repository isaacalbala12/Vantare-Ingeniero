# v0.8 — Pit Manager LMU Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pit stop por voz en LMU: leer plan, confirmar, ejecutar REST (`LMUPitMenuAPI` parity CC) — fuel, tyres, repairs, virtual energy, fuel ration.

**Architecture:** Extender `PitMenuClient` existente + comandos PTT dedicados + confirmación voz (`PIT_MENU_CONFIRM_WRITES`). Guards: pit lane / menu open / dry_run off only with confirm.

**Tech Stack:** Python 3.12, `lmu_api.py` REST, pytest + httpx mock.

**Orquestador:** [`2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md)

**Referencia CC:** `LMUPitMenuAPI.cs`, [`../../crewchief-comparison.md`](../../crewchief-comparison.md) § PitManager

---

## Preconditions

- [ ] v0.7 GATE ✅
- [ ] `backend/src/intelligence/crewchief_events/pit_menu.py` exists
- [ ] LMU API mock tests in `test_lmu_api.py`

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Modify | `backend/src/intelligence/crewchief_events/pit_menu.py` |
| Modify | `backend/src/intelligence/pilot_tool_executor.py` |
| Modify | `backend/src/services/lmu_api.py` |
| Modify | `backend/src/config.py` (`PIT_MENU_DRY_RUN`, `PIT_MENU_CONFIRM_WRITES`) |
| Create | `backend/tests/test_pit_manager_voice.py` |

### Files FORBIDDEN

- iRacing pit, Go, shared-telemetry

---

## Task 1: Read plan + summarize voice

- [ ] **Step 1: Test**

```python
@pytest.mark.asyncio
async def test_pit_plan_summary_includes_fuel_and_tyres(mock_lmu_menu):
    client = PitMenuClient(mock_lmu_menu, dry_run=True)
    summary = await client.summarize_plan()
    assert "fuel" in summary.lower() or "combustible" in summary.lower()
```

- [ ] **Step 2: Implement `summarize_plan()`** from `get_pit_menu()` JSON
- [ ] **Step 3: PTT tool `pit_plan_summary`**
- [ ] **Step 4: Commit**

---

## Task 2: Write commands P0

- [ ] Tools: `pit_add_fuel_litres`, `pit_fuel_to_end`, `pit_change_tyres_all`, `pit_change_tyres_front`, `pit_change_tyres_rear`, `pit_fix_body`, `pit_fix_all`, `pit_fix_none`
- [ ] LMU-specific: `pit_virtual_energy_pct`, `pit_fuel_ration_pct`
- [ ] Each write: require `confirm=True` in args or second PTT "confirm"

---

## Task 3: Guards

- [ ] `assert_pit_context()` — `in_pits` or pit menu API reachable
- [ ] Test dry_run=True never POSTs
- [ ] Test reject when race not running

---

## Task 4: Voice responses

- [ ] Localized messages ES (+ EN if 0.6 done) via phrase catalog
- [ ] IMMEDIATE priority for "rejected" errors

---

## Task 5: GATE v0.8

- [ ] Bump 0.8.0
- [ ] `pytest tests/test_pit_manager_voice.py tests/test_lmu_api.py -q`
- [ ] Manual LMU pit lane: dry_run off + confirm → menu updates (evidence `.omo/evidence/pit-v08.md`)

---

## GATE v0.8

| Check | Expected |
|-------|----------|
| dry_run default safe | no POST in tests |
| confirm required | 403/ message without confirm |
| P0 commands | matrix 8/8 PASS |
| `verify_beta_gate.ps1` | PASS |
