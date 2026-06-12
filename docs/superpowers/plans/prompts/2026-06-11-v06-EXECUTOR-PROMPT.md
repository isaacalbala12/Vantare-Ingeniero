# v0.6 English App-Wide Executor Prompt

You are the EXECUTOR for Vantare Ingeniero IA v0.6. Work in the existing repository.

Read only this prompt plus `docs/superpowers/plans/2026-06-11-roadmap-v06-english.md`. Do not jump to v0.7 work.

## Mission

Implement v0.6: English support for the whole app, in the simplest possible code.

This means:

- `voiceLanguage` controls what is heard: spotter phrases, trigger phrases, number/time speech, TTS voice selection and ASR/PTT language.
- `uiLanguage` controls what is seen: Hub labels, buttons, settings text, visible status strings and radio overlay text.
- Existing installs must stay Spanish by default.
- A future onboarding flow will choose language on first launch. Do not build onboarding in v0.6.

## Non-negotiable simplicity rule

The product owner has no coding background. Prefer code that is boring, obvious and easy to undo.

Do:

- Use small dictionaries and plain functions.
- Keep changes local to v0.6 files.
- Write tests before implementation.
- Preserve Spanish behavior.
- Add only the minimum wiring needed.

Do not:

- Add a frontend i18n framework.
- Add auto language detection.
- Add onboarding.
- Refactor large components just to make translation elegant.
- Touch `shared-telemetry/`.
- Add Go, Suite, iRacing, CrewChiefV4 runtime, telemetry HUD overlays or a second backend executable.
- Commit unless the user explicitly asks.

## Baseline before edits

Run from repo root:

```powershell
cd backend
python -m pytest tests/test_spotter.py tests/test_voice_loop.py tests/test_main_lifecycle_contract.py -q --tb=line
cd ..\frontend
npm test
cd ..
```

If baseline fails, stop and report the failing commands and first failing tests.

## Task 1: Backend phrase catalog locale

Files:

- Modify: `backend/src/intelligence/phrase_catalog.py`
- Create: `backend/src/data/spotter_phrases_en.json`
- Create: `backend/src/data/trigger_phrases_en.json`
- Create: `backend/tests/test_phrase_catalog_en.py`

Steps:

- [ ] Inspect existing Spanish files:

```powershell
Get-Content -Raw backend/src/data/spotter_phrases_es.json
Get-Content -Raw backend/src/data/trigger_phrases_es.json
Get-Content -Raw backend/src/intelligence/phrase_catalog.py
```

- [ ] Write failing tests in `backend/tests/test_phrase_catalog_en.py`:

```python
from src.intelligence.phrase_catalog import PhraseCatalog


def test_loads_english_spotter_left():
    catalog = PhraseCatalog.load(locale="en")
    text = str(catalog.spotter["left"]).lower()
    assert "left" in text


def test_english_spotter_has_same_keys_as_spanish():
    es = PhraseCatalog.load(locale="es")
    en = PhraseCatalog.load(locale="en")
    assert set(en.spotter.keys()) == set(es.spotter.keys())


def test_english_triggers_have_existing_spanish_keys():
    es = PhraseCatalog.load(locale="es")
    en = PhraseCatalog.load(locale="en")
    missing = set(es.triggers.keys()) - set(en.triggers.keys())
    assert missing == set()
```

- [ ] Run the failing test:

```powershell
cd backend
python -m pytest tests/test_phrase_catalog_en.py -q --tb=line
cd ..
```

Expected: fail because `PhraseCatalog.load(locale=...)` or EN files do not exist.

- [ ] Implement `PhraseCatalog.load(locale: str = "es")` with only `es` and `en` allowed. Keep `load_merged()` behavior intact for existing editable phrases.

- [ ] Create EN JSON files by copying ES key structure and translating values. Preserve profile names and placeholders.

- [ ] Run:

```powershell
cd backend
python -m pytest tests/test_phrase_catalog_en.py tests/test_spotter.py -q --tb=line
cd ..
```

Expected: pass.

## Task 2: English number speech

Files:

- Create: `backend/src/intelligence/number_speech.py`
- Modify if needed: `backend/src/intelligence/time_format.py`
- Create: `backend/tests/test_number_speech_en.py`

Steps:

- [ ] Write failing tests:

```python
from src.intelligence.number_speech import format_fuel_litres_en, format_gap_en, format_lap_time_en


def test_gap_one_second_uses_words():
    assert format_gap_en(1.0) == "one second"


def test_gap_decimal_uses_words_not_raw_digits():
    spoken = format_gap_en(1.2)
    assert "one point two" in spoken
    assert "1.2" not in spoken


def test_fuel_litres_pluralization():
    assert format_fuel_litres_en(1) == "one litre"
    assert format_fuel_litres_en(2) == "two litres"


def test_lap_time_english_words():
    spoken = format_lap_time_en(92.345)
    assert "one minute" in spoken
    assert "thirty two" in spoken
    assert "point three four five" in spoken
```

- [ ] Run:

```powershell
cd backend
python -m pytest tests/test_number_speech_en.py -q --tb=line
cd ..
```

- [ ] Implement minimal helpers for the tested range. Keep them deterministic and dependency-free.

- [ ] Run:

```powershell
cd backend
python -m pytest tests/test_number_speech_en.py -q --tb=line
cd ..
```

## Task 3: English TTS/personality voices

Files:

- Modify: `backend/src/intelligence/personality_pack.py`
- Add or update focused backend test near existing personality/TTS tests.

Steps:

- [ ] Inspect existing personality tests and model:

```powershell
rg "PersonalityPack|ttsVoice|voice" backend/tests backend/src/intelligence backend/src/services -n
```

- [ ] Add tests that verify English defaults exist. Use these target voices unless the existing code already defines a better naming pattern:

```text
engineer: en-GB-RyanNeural
spotter: en-US-JennyNeural
```

- [ ] Implement the smallest API needed to select voices by locale while keeping Spanish defaults unchanged.

- [ ] Run the focused tests plus:

```powershell
cd backend
python -m pytest tests/test_voice_loop.py -q --tb=line
cd ..
```

## Task 4: Config language fields and backend sync

Files:

- Modify: `frontend/src/store/config.ts`
- Modify likely: `frontend/src/hub/forms/appConfigKeys.ts`
- Modify likely: `frontend/src/services/configUpdateWs.ts`
- Modify backend config handling only where current config updates are parsed.
- Add/update frontend tests: `frontend/src/__tests__/configStore.test.ts`, `frontend/src/__tests__/configUpdatePayload.test.ts`, `frontend/src/__tests__/languageConfig.test.ts`

Steps:

- [ ] Add types:

```ts
export type AppLanguage = "es" | "en";
```

- [ ] Add `uiLanguage: AppLanguage` and `voiceLanguage: AppLanguage` to `AppConfig`.

- [ ] Bump frontend config schema from 5 to 6.

- [ ] Default both fields to `"es"` for new and migrated installs.

- [ ] Ensure saved config payload includes both fields.

- [ ] Add tests for default, migration and config update payload.

- [ ] Run:

```powershell
cd frontend
npm test -- --run configStore languageConfig configUpdatePayload
cd ..
```

## Task 5: Minimal frontend UI dictionary

Files:

- Create: `frontend/src/i18n/strings.ts`
- Create: `frontend/src/__tests__/i18nStrings.test.ts`
- Modify visible text in normal-use surfaces:
  - `frontend/src/components/ConfigTab.tsx`
  - `frontend/src/hub/HubRoot.tsx`
  - `frontend/src/hub/sections/*.tsx` only where text is visible in main settings
  - `frontend/src/overlay/OverlayApp.tsx`
  - `frontend/src/overlay/variants/*.tsx` only for visible radio labels

Steps:

- [ ] Create `strings.ts` with this simple shape:

```ts
export type AppLanguage = "es" | "en";

export const STRINGS = {
  es: {
    settings: "Configuración",
  },
  en: {
    settings: "Settings",
  },
} as const;

export type StringKey = keyof typeof STRINGS.es;

export function t(language: AppLanguage | undefined, key: StringKey): string {
  return STRINGS[language ?? "es"][key];
}
```

- [ ] Add tests:

```ts
import { describe, expect, it } from "vitest";
import { STRINGS, t } from "../i18n/strings";

describe("i18n strings", () => {
  it("has the same keys in Spanish and English", () => {
    expect(Object.keys(STRINGS.en).sort()).toEqual(Object.keys(STRINGS.es).sort());
  });

  it("falls back to Spanish by default", () => {
    expect(t(undefined, "settings")).toBe(STRINGS.es.settings);
  });
});
```

- [ ] Expand `STRINGS` only with keys needed by visible text you touch. Keep names plain, for example `save`, `audio`, `voice`, `advanced`, `testConnection`.

- [ ] In components, read `uiLanguage` from `useAppStore()` and call `t(uiLanguage, "key")`.

- [ ] Keep old Spanish text where it is dynamic history from the backend or user-supplied phrases.

- [ ] Run:

```powershell
cd frontend
npm test -- --run i18nStrings
npm test
cd ..
```

## Task 6: Language selector UI

Files:

- Modify: `frontend/src/components/ConfigTab.tsx`
- Add/update focused frontend test if existing test harness covers config UI.

Steps:

- [ ] Add local state for `uiLanguage` and `voiceLanguage`.

- [ ] Include both fields in `buildConfigPayload()` and `applyLoadedConfig()`.

- [ ] Add a simple selector in advanced or profiles/settings area:

```tsx
<select value={uiLanguage} onChange={(event) => setUiLanguage(event.target.value as AppLanguage)}>
  <option value="es">Español</option>
  <option value="en">English</option>
</select>
```

```tsx
<select value={voiceLanguage} onChange={(event) => setVoiceLanguage(event.target.value as AppLanguage)}>
  <option value="es">Español</option>
  <option value="en">English</option>
</select>
```

- [ ] Save must update localStorage and send WS config update with both fields.

- [ ] Run:

```powershell
cd frontend
npm test -- --run configTab configUpdatePayload languageConfig i18nStrings
cd ..
```

## Task 7: Final gate

Run:

```powershell
cd backend
python -m pytest tests/test_phrase_catalog_en.py tests/test_number_speech_en.py tests/test_spotter.py tests/test_voice_loop.py tests/test_main_lifecycle_contract.py -q --tb=line
cd ..\frontend
npm test
cd ..
git diff --stat
git diff --name-only
```

Check the diff manually:

- No `shared-telemetry/`.
- No Go/Suite/iRacing.
- No telemetry HUD overlay scope.
- No CrewChiefV4 runtime.
- No second exe/supervisor.
- No mass refactor of `backend/src/crewchief_events/modules/**`.

Manual smoke:

- Start the app.
- Set `uiLanguage=en`.
- Main Hub/settings and radio overlay visible labels are in English.
- Set `voiceLanguage=en`.
- Spotter phrase for left-side car is audible as "car left" or equivalent.
- Switch both back to Spanish and confirm Spanish still works.

Report results to the orchestrator. Do not bump version, update changelog, tag, release or commit unless the user explicitly asks.
