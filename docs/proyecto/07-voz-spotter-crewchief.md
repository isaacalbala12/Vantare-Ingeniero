# 07 — Voz, spotter y paridad CrewChief

---

## Contrato de voz (normativo)

**Documento:** [`../voice-contract.md`](../voice-contract.md)

Define invariantes **I1–I5**:

| ID | Regla |
|----|-------|
| I1 | Bloqueos TTS no silenciosos en debug |
| I2 | PTT/advice siempre pasan toggles engineer |
| I3 | `speakOnlyWhenSpokenTo` no bloquea spotter |
| I4 | Categorías `gaps`, `system`, `spotter` interno → sin TTS |
| I5 | Cambiar default config → doc + test migración |

**Nota arquitectura v0.2.14+:** el diagrama del voice-contract aún muestra TTS vía HTTP en frontend; la **implementación actual** reproduce en `backend/voice/service.py` (pygame). Los tests y categorías siguen siendo válidos; alinear diagrama es deuda doc.

Verificación: `scripts/verify_voice_contract.py`, `backend/tests/test_spotter_audio_contract.py`.

---

## Pipeline audio actual (backend)

```
Mensaje (spotter | trigger | PTT | CC module)
        │
        ▼
VoiceService / play_command
        │
        ▼
TTSManager (Edge | Gemini | Piper | ElevenLabs)
        │
        ▼
Cola prioridad (CRITICAL > HIGH > MEDIUM > LOW)
        │
        ▼
moderator (braking defer, preemption)
        │
        ▼
pygame player
        │
        ▼
WS voice_playback_start/end → overlay
```

---

## Spotter

### Lógica
- Evaluación ~20 Hz en **race loop global** (no por cliente WS)
- Geometría cartesiana: left/right/ahead/behind, three-wide, overlap
- Exclusiones: pits, coches parados (configurable Hub)

### Frases
- `PhrasePicker` + `spotter_phrases_es.json`
- Variantes `frase A|frase B|frase C` por key
- Perfil: formal / standard / aggressive
- Overrides usuario v0.4 en AppData

### Caché TTS
- `SpotterPhraseCache` precalienta WAV Edge
- Bypass si spotter usa Gemini (no WAV Edge stale)
- `invalidate_all()` tras guardar frases

Tests: `test_spotter.py`, `test_cartesian_spotter.py`, `test_spotter_e2e.py`, fixtures JSON.

---

## CrewChief events (ingeniero determinista)

### Cutover Task 48
Ruta principal post-cutover: **CrewChiefEventSuite @ 20 Hz**, no batch LLM commentary.

`commentary_orchestrator.py` = LEGACY ruta B (debounce batch); gate proactivity v0.5.

### Módulos principales

| Módulo | Eventos típicos |
|--------|-----------------|
| fuel | Low fuel tiers, FCY consumption |
| flags | FCY, safety car, pits closed |
| lap_times | Lap complete, fast lap, PB |
| pearls | Overtake, comeback, wisdom (frequency v0.5) |
| damage | Bodywork, suspension |
| tyre_monitor | Wear, pressures |
| pit_stops | Window, time lost |
| rain_monitor | Rain intensity |
| opponent_messages | Gaps, being passed |

### Personalidad v0.5

- `PersonalityPack.should_emit_proactive(priority)` filtra emisiones CC/commentary
- `pearl_frequency` → `pearls.py` + `pearls_of_wisdom.py`
- `sweary` → suffix tono LLM + frases coloquiales

---

## Triggers IntelligenceEngine

`triggers.py` — condiciones que pueden emitir alertas LLM o deterministas:

- FuelCritical, SafetyCar, BrakeWear, TyreDeg, Hybrid, Weather, PitWindow, …

Prioridades y categorías alimentan voice contract y toggles Hub.

---

## TTS routing (v0.3+)

| Rol | Config Hub | Servicio |
|-----|------------|----------|
| Ingeniero | `ttsProviderEngineer` | edge / gemini |
| Spotter | `ttsProviderSpotter` | edge / gemini |

Gemini requiere `GEMINI_API_KEY` en backend `.env`.

---

## Comparativa CrewChief

Matriz feature-por-feature: [`../crewchief-comparison.md`](../crewchief-comparison.md).

Pipelines arquitectónicos: [`../architecture/pipelines/`](../architecture/pipelines/).

Porting notes: [`../architecture/crewchief-porting-notes.md`](../architecture/crewchief-porting-notes.md).

---

## Defaults release (comportamiento piloto nuevo)

| Setting | Default | Efecto |
|---------|---------|--------|
| `engineerEnabled` | false | Sin triggers proactivos hasta activar |
| `spotterEnabled` | false | Spotter off hasta activar |
| `speakOnlyWhenSpokenTo` | true | Solo PTT + spotter (no ingeniero proactivo) |

Migración config v1→v2 documentada en voice-contract §2.

---

## QA audio en pista

Checklists:

- [`../qa/electron-smoke-checklist.md`](../qa/electron-smoke-checklist.md)
- Evidencia: `.omo/evidence/audio-lmu-validation.md` (objetivo v0.9)

Scripts:

- `scripts/verify_beta_gate.ps1`
- `scripts/verify_audio_pipeline.py`
