# v0.4 — Frases editables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir al usuario **editar, exportar e importar** frases de triggers/spotter; overrides en `%APPDATA%` con fallback a defaults empaquetados.

**Architecture:** `PhraseCatalog` carga merge: `defaults/` (bundle) + `user_phrases.json` (AppData). Hub UI JSON editor + import/export. Validación schema en backend antes de persistir.

**Tech Stack:** Python 3.12, FastAPI router, Electron Hub, Vitest, pytest.

**Orquestador:** [`2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md)

---

## Preconditions

- [ ] v0.3 GATE ✅
- [ ] `PhraseCatalog` existe (`phrase_catalog.py`)

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Modify | `backend/src/intelligence/phrase_catalog.py` |
| Create | `backend/src/persistence/phrase_store.py` |
| Create | `backend/src/routers/phrases.py` |
| Modify | `backend/src/main.py` (router) |
| Modify | `frontend/src/hub/` (tab Perfiles o Audio → Frases) |
| Create | `backend/tests/test_phrase_store.py`, `frontend/src/__tests__/phraseEditor.test.ts` |

### Files FORBIDDEN

- `shared-telemetry/**`, Go, iRacing, race_loop refactor

---

## Task 1: PhraseStore (AppData merge)

**Files:**
- Create: `backend/src/persistence/phrase_store.py`
- Create: `backend/tests/test_phrase_store.py`

- [ ] **Step 1: Failing test — override wins**

```python
def test_user_override_replaces_default_variant(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_PHRASES_DIR", str(tmp_path))
    store = PhraseStore()
    store.save_user({"spotter": {"left": ["Custom izquierda"]}})
    cat = store.load_merged_catalog()
    assert "Custom izquierda" in cat.get_spotter("left").variants
```

- [ ] **Step 2: Implement `PhraseStore`** — path `%APPDATA%/Vantare/phrases/user_phrases.json`, merge shallow por key, invalid empty → skip override.

- [ ] **Step 3: pytest PASS + commit**

---

## Task 2: REST export/import

**Files:**
- Create: `backend/src/routers/phrases.py`

- [ ] **Step 1: Endpoints**

```
GET  /phrases          → merged catalog JSON
GET  /phrases/defaults → bundled only
PUT  /phrases          → validate + save user overrides
POST /phrases/import   → replace user file (schema validate)
GET  /phrases/export   → download user overrides
```

- [ ] **Step 2: Test `test_phrase_store.py` + httpx TestClient**

- [ ] **Step 3: Commit**

---

## Task 3: Hub phrase editor

**Files:**
- Modify Hub (nueva sección o sub-tab en Audio)

- [ ] **Step 1: Vitest** — import JSON válido actualiza store vía API mock.

- [ ] **Step 2: UI** — lista keys spotter/trigger, textarea variants (una por línea), Export/Import/Reset to defaults.

- [ ] **Step 3: `npm test -- phraseEditor` PASS**

- [ ] **Step 4: Commit**

---

## Task 4: Hot-reload cache spotter

**Files:**
- Modify: `backend/src/voice/spotter_cache.py`

- [ ] **Step 1: On `PUT /phrases`** → invalidate spotter WAV cache keys afectadas + warm critical phrases async.

- [ ] **Step 2: Test** `test_spotter_cache.py` invalidation hook.

- [ ] **Step 3: Commit**

---

## Task 5: Release v0.4 GATE

- [ ] Bump `0.4.0`, CHANGELOG
- [ ] `verify_beta_gate.ps1` PASS
- [ ] Manual: editar frase "left" → spotter audible con texto custom en dev

---

## GATE v0.4

| Check | Expected |
|-------|----------|
| Override persiste tras restart backend | PASS |
| Import JSON inválido → 422 | PASS |
| Reset defaults restaura bundle | PASS |
| `verify_beta_gate.ps1` | PASS |
