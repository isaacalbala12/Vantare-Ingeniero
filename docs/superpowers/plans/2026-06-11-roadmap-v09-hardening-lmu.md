# v0.9 — Hardening LMU + validación multi-circuito Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release **production-quality** en LMU: instalador fiable, auto-update verificado, `duck_lmu` en bundle, checklist multi-circuito con evidencia. **Sin** Go, launcher, iRacing.

**Architecture:** Solo scripts CI/release + fixes P0 encontrados en smoke. Monolito sin cambios arquitectónicos.

**Tech Stack:** PowerShell gates, PyInstaller, electron-builder, Rust `duck_lmu`.

**Orquestador:** [`2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md)

---

## Preconditions

- [ ] v0.8 GATE ✅

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Modify | `scripts/verify-release.ps1`, `verify_beta_gate.ps1`, `build-desktop.ps1` |
| Modify | `frontend/electron-builder.yml` (duck_lmu path) |
| Modify | `.github/workflows/release-desktop.yml` |
| Create | `docs/qa/lmu-multi-circuit-checklist.md` |
| Create | `.omo/evidence/lmu-multi-circuit-YYYYMMDD.md` |

### Files FORBIDDEN

- Go, Suite, iRacing, shared-telemetry
- New voice features (→ 1.0)
- In-game telemetry overlays

---

## Task 1: duck_lmu en bundle

- [ ] **Step 1: Build duck**

```powershell
powershell -File scripts/build-duck-lmu.ps1
```

- [ ] **Step 2: Verify** `frontend/release/win-unpacked/resources/duck_lmu.exe` OR extraResources path exists post-build
- [ ] **Step 3: Wire `DuckingController`** to spawn/use bundled path
- [ ] **Step 4: Test** `backend/tests/test_ducking.py` if exists or create minimal

---

## Task 2: Auto-update integrity gate

- [ ] **Step 1: Add step to `verify-release.ps1`**

```powershell
# Compare local setup.exe size vs gh release asset when tag matches package.json
$localSize = (Get-Item $setupExe).Length
# fail if mismatch when -VerifyRemote
```

- [ ] **Step 2: Document** en `docs/launch/release-process.md` — always verify asset bytes post-upload
- [ ] **Step 3: CI** `release-desktop.yml` uploads exe + latest.yml atomically

---

## Task 3: Multi-circuit checklist

- [ ] **Step 1: Create `docs/qa/lmu-multi-circuit-checklist.md`**

Minimum matrix:

| Circuito | Condición | Spotter | Engineer | Pit 0.8 | Voz OK |
|----------|-----------|---------|----------|---------|--------|
| Le Mans | dry day | | | | |
| Spa | wet | | | | |
| Monza | night | | | | |

- [ ] **Step 2: Execute manual** — pilot fills `.omo/evidence/lmu-multi-circuit-YYYYMMDD.md`
- [ ] **Step 3: Orquestador sign-off** — all cells ✅

---

## Task 4: Full release GATE

- [ ] **Step 1:**

```powershell
powershell -File scripts/verify-release.ps1
powershell -File scripts/verify_beta_gate.ps1
powershell -File scripts/build-desktop.ps1
powershell -File scripts/verify_bundle_startup.ps1
```

- [ ] **Step 2: Bump 0.9.0** — promote stable (not prerelease)
- [ ] **Step 3: Tag + gh release** (user request only)

---

## GATE v0.9

| Check | Expected |
|-------|----------|
| `verify-release.ps1` | ALL PASS |
| `verify_beta_gate.ps1` | PASS |
| Asset size GitHub = local | match bytes |
| Multi-circuit evidence | 3+ tracks documented |
| duck_lmu bundled | file exists in release |
| No Go/iRacing code in diff | rg clean |

---

## Forbidden en 0.9

- ❌ Launcher Suite
- ❌ Companion API
- ❌ iRacing mapper
- ❌ Voice cloning
