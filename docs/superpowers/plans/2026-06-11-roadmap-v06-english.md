# v0.6 — Inglés Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Soporte **inglés** completo en toda la app: interfaz Hub/overlay, frases spotter/triggers EN, TTS EN por perfil, localización de números/tiempos estilo CrewChief NumberProcessing.

**Architecture:** `PhraseCatalog` locale-aware (`es`/`en`); `PersonalityPack` per-locale voices; `time_format.py` + nuevo `number_speech.py` para EN. Config `uiLanguage` + `voiceLanguage`. Frontend i18n debe ser mínimo y explícito: un diccionario local de strings, sin librerías pesadas ni refactor masivo.

**Tech Stack:** Python 3.12, JSON phrase files, Edge EN voices, pytest, React/TypeScript, Vitest.

**Simplicity rule:** El usuario no programa. Priorizar código directo, fácil de leer y reversible. No introducir frameworks i18n, no cambiar la arquitectura, no crear abstracciones complejas, no tocar pantallas fuera de v0.6.

**Orquestador:** [`2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md)

---

## Preconditions

- [ ] v0.5 GATE ✅
- [ ] `PhraseCatalog` + user overrides (0.4)

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Create | `backend/src/data/spotter_phrases_en.json`, `trigger_phrases_en.json` |
| Modify | `backend/src/intelligence/phrase_catalog.py` |
| Create | `backend/src/intelligence/number_speech.py` |
| Modify | `backend/src/intelligence/time_format.py`, `driver_names.py` |
| Modify | `backend/src/intelligence/personality_pack.py` (EN profiles) |
| Modify | `frontend/src/store/config.ts`, Hub idioma |
| Create | `frontend/src/i18n/strings.ts` |
| Modify | Textos principales en `frontend/src/hub/`, `frontend/src/components/`, `frontend/src/overlay/` según sea necesario |
| Create | `backend/tests/test_number_speech_en.py`, `test_phrase_catalog_en.py` |
| Create | `frontend/src/__tests__/i18nStrings.test.ts`, `frontend/src/__tests__/languageConfig.test.ts` |

### Files FORBIDDEN

- `shared-telemetry/**`
- Go / Suite / iRacing files
- CrewChiefV4 runtime files
- Any new supervisor process or second backend exe
- Massive refactors of `backend/src/crewchief_events/modules/**`

### Explicitly out of scope

- Onboarding language selection
- Automatic OS language detection
- Runtime download of translations
- Full translation management platform
- New visual telemetry overlay in Vantare

---

## Task 1: PhraseCatalog i18n

- [ ] **Step 1: Test**

```python
def test_catalog_loads_en_left():
    cat = PhraseCatalog.load(locale="en")
    assert "left" in cat.get_spotter("left").variants[0].lower() or cat.get_spotter("left")
```

- [ ] **Step 2: `load(locale="es"|"en")`** — file suffix `_es.json` / `_en.json`
- [ ] **Step 3: Populate `spotter_phrases_en.json`** — paridad keys con ES
- [ ] **Step 4: Commit**

---

## Task 2: NumberProcessing EN

- [ ] **Step 1: Test**

```python
from src.intelligence.number_speech import format_gap_en
assert "one second" in format_gap_en(1.0).lower()
assert "1.2" not in format_gap_en(1.2)  # palabras, no dígitos crudos en voz
```

- [ ] **Step 2: Implement `number_speech.py`** — gaps, lap times, fuel litres
- [ ] **Step 3: Wire spotter/triggers** — usar formatter según `voiceLanguage`
- [ ] **Step 4: Commit**

---

## Task 3: TTS voices EN

- [ ] Extend profiles: `en-GB-RyanNeural`, `en-US-JennyNeural` defaults
- [ ] `TTSManager` voice from profile + locale
- [ ] Test synthesize path mock

---

## Task 4: Hub language selector + app UI language

- [ ] `voiceLanguage` + `uiLanguage` in config schema v6
- [ ] Hub → Avanzado or Perfiles with a simple selector
- [ ] Minimal frontend dictionary: `t(config.uiLanguage, key)`
- [ ] Translate visible primary Hub/overlay strings touched by normal use
- [ ] Vitest config migration + dictionary coverage

---

## Task 5: GATE v0.6

- [ ] Bump 0.6.0
- [ ] `verify_beta_gate.ps1` PASS
- [ ] Manual EN session: spotter "car left" audible

---

## GATE v0.6

| Check | Expected |
|-------|----------|
| ES regression | full pytest PASS |
| EN spotter keys parity | `test_phrase_catalog_en` |
| Number speech EN | `test_number_speech_en` |
| Config sync locale | `test_config_sync_ws` |
| UI language | `i18nStrings.test.ts`, `languageConfig.test.ts` |
| Manual UI smoke | Hub and radio overlay readable in English when `uiLanguage="en"` |
