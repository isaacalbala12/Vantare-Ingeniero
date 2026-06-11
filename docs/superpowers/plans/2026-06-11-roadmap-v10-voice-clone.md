# v1.0 — Clonación de voz básica Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** **Un timbre clonado por perfil** con muestra de audio del usuario, consentimiento explícito, fallback Gemini/Edge si falla. Monolito intacto.

**Architecture:** Nuevo `ClonedVoiceService` en backend; samples en `%APPDATA%/Vantare/voices/`; `TTSManager` provider chain: `clone` → `gemini` → `edge`. Hub wizard grabación (WebM) → upload → backend validate.

**Tech Stack:** Python 3.12, proveedor TTS clonación TBD (ElevenLabs instant clone / OpenAI / local XTTS eval in ADR), Electron MediaRecorder, pytest.

**Orquestador:** [`2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md)

---

## Preconditions

- [ ] v0.9 GATE ✅
- [ ] Gemini + Edge pipeline stable

---

## Task 0: ADR proveedor clonación (BLOCKING)

- [ ] **Step 1: Create `docs/decisions/ADR-006-voice-cloning-provider.md`**
- Compare: ElevenLabs IVC, OpenAI, local XTTS — latency, cost, ToS, offline
- **Decision required before Task 2**

---

## Task 1: Voice sample store

**Files:**
- Create: `backend/src/persistence/voice_clone_store.py`
- Create: `backend/tests/test_voice_clone_store.py`

- [ ] **Step 1: Test save/load sample metadata**

```python
def test_store_saves_wav_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_VOICES_DIR", str(tmp_path))
    store = VoiceCloneStore()
    store.save_sample("profile-1", b"RIFF...", consent_version="1")
    assert store.has_clone("profile-1")
```

- [ ] **Step 2: Implement** — max 30s sample, WAV only, consent timestamp

---

## Task 2: ClonedVoiceService

- [ ] Implement provider adapter per ADR-006
- [ ] `TTSManager` fallback chain test
- [ ] Never send sample to LLM text endpoint — TTS only

---

## Task 3: Hub wizard

- [ ] Perfil → Voz → Grabar 15–30s → preview → guardar
- [ ] Checkbox consentimiento obligatorio
- [ ] Vitest + manual mic test

---

## Task 4: Legal + UX

- [ ] Copy consent in UI (ES/EN)
- [ ] Delete clone button → removes AppData files

---

## Task 5: GATE v1.0

- [ ] Bump 1.0.0
- [ ] `verify_beta_gate.ps1` PASS
- [ ] Manual: cloned profile speaks engineer line audible
- [ ] Fallback test: disable clone API → Edge speaks without crash

---

## GATE v1.0

| Invariante | Test |
|------------|------|
| I1 No clone without consent | store rejects |
| I2 Fallback always works | test provider None |
| I3 Sample never in LLM prompt | code review + grep |
