# Auditoría CC → Vantare (Jun 2026)

Auditoría trigger-por-trigger y pipeline-por-pipeline frente a Crew Chief V4 (LMU).  
**Objetivo:** cerrar deltas antes de la revisión de código + verificación de pipelines.  
**Referencias:** `docs/crewchief-comparison.md` (desactualizado en spotter), `.omo/evidence/audio-lmu-validation.md`, tests CI.

**Leyenda:** ✅ paridad | ⚠️ parcial / diseño distinto | ❌ gap | 🔧 fix recomendado en code review

---

## 1. Resumen ejecutivo

| Área | Estado | Notas |
|------|--------|-------|
| Spotter lateral (#1–5) | ✅ | Defaults CC, clear/3-wide, limiter engage/disengage validados LMU |
| Spotter sesión (#6–10) | ⚠️ | Anti-spam OK; fuel finish-safe OK; **gaps solo UI** (CC tiene voz opcional) |
| Ingeniero ALERT (#11–13) | ✅ | Edge-once; CI verde |
| Ingeniero LLM (#14–16) | ✅ | Edge + fuel finish-safe; CI verde |
| Audio / PTT (#17–24) | ✅ CI | LMU pendiente |
| Commentary proactivo | ⚠️ | Fuel finish-safe en monitors; gaps spotter UI-only |
| Perlas | ⚠️ | Implementadas; modelo distinto a CC (frecuencia 0–10) |
| Verbosidad | ⚠️ | 3 niveles OK; falta “prioritize under pressure” / quali lap CC |
| PitManager voz | ❌ | Fuera de scope alpha; CC 20+ archivos |

**Top 5 deltas restantes (post-fix Jun 2026):**

1. ⚠️ **Gaps spotter** — Vantare: UI-only (`category=gaps`, priority 1); CC: `enable_gap_messages` + Timings con voz opcional.
2. ⚠️ **Triple fuel** — spotter `<1` + trigger `<3` + commentary `<3` pueden solaparse en escenarios marginales (CC separa “running on fumes” vs fuel report); mitigado con finish-safe.
3. ⚠️ **Perlas** — max 2/carrera vs slider CC 0–10.
4. ⚠️ **Verbosity** — falta `prioritize_messages_under_pressure` / quali lap CC.
5. ❌ **PitManager voz** — fuera de scope alpha.

~~P0 edge-once / fuel commentary~~ — cerrado Jun 2026.

---

## 2. Spotter — checklist LMU #1–10

| # | CC (`Spotter.cs` / props) | Vantare | Paridad | Evidencia CI |
|---|---------------------------|---------|---------|--------------|
| 1 | Car left/right, hold repeat | `spotter_state` + `cartesian_spotter` | ✅ | `test_spotter_cc_parity`, `verify_spotter_pipeline` |
| 2 | Clear delay ~0.15s | `SPOTTER_CLEAR_DELAY_S=0.15` | ✅ | `test_spotter_state` |
| 3 | Three-wide L/R | `in_the_middle`, bounce 1.5s | ✅ | `test_spotter_state` |
| 4 | Pit limiter engage (grace) | grace 3s, ventana 8s, cooldown 30s | ✅ | LMU usuario + `test_spotter` |
| 5 | Pit limiter disengage (delay) | delay 2s + reintentos | ✅ | LMU usuario |
| 6 | Fuel crítico | `<1` vuelta, edge-once + **finish-safe** | ✅ | `test_fuel_safety`, `test_spotter` |
| 7 | SC / FCY | edge-once | ✅ | `test_spotter` anti-spam |
| 8 | Última vuelta | edge-once | ✅ | `test_spotter` |
| 9 | Daño | edge-once | ✅ | `test_spotter` |
| 10 | Gap estrecho | CC: voz si `enable_gap_messages` | ⚠️ | **Solo UI** — `alertVoice` excluye `gaps`; cooldown 40s default |

**Qualifying / timetrial:** CC `enable_spotter_in_timetrial` (default off). Vantare `SPOTTER_OFF_QUALIFYING=True` — sin lateral/gaps/damage/proximity; limiter + SC + fuel siguen. ✅ `test_qualifying_silent_no_proximity`.

**Comandos voz:** CC grammar “spot / don't spot”. Vantare `parseSpotterCommand` → WS `spotter_command` → ack UI-only (`category=spotter`). ✅ #22.

---

## 3. Ingeniero — ALERT_ONLY (#11–13)

| Trigger | CC módulo | Vantare | Edge-once | CI |
|---------|-----------|---------|-----------|-----|
| Frenos >80% | TyreMonitor / brakes | `BrakeWearCriticalTrigger` | ✅ | `test_audio_trigger_matrix` |
| Multiclase | `MulticlassWarnings` | `MulticlassWarningTrigger` | ✅ por escenario | idem |
| Penalización | `Penalties` | `PenaltyMonitorTrigger` | ✅ en cambio | idem |

**Nota CC:** multiclase también en spotter (frases “doblando”); Vantare spotter proximity + trigger ingeniero (no duplicado en `proactive_monitors` — `test_multiclass_not_in_proactive_commentary`).

---

## 4. Ingeniero — LLM_REQUIRED (triggers restantes)

| Trigger | CC analogía | Condición Vantare | Edge-once | Delta |
|---------|-------------|-------------------|-----------|-------|
| **FuelCritical** #14 | Fuel + LLM | `<3` + **no finish-safe** | ✅ | — |
| **FlagsMonitor** #15 | `FlagsMonitor` | transiciones bandera | ✅ | — |
| **PitWindowOpened** #16 | Strategy / PitStops | ventana abierta | ✅ | — |
| PitWindowClosing | PitStops | ≤2 vueltas en ventana | ✅ | — |
| TiresThermal | EngineMonitor | temp >105 | ✅ edge | — |
| TyreDegAccel | TyreMonitor | deg >25% | ✅ edge | — |
| HybridDeployMap | OvertakingAids | SOC crítico + descarga neta | ✅ edge | — |
| WeatherChange | ConditionsMonitor | rain >30% | ✅ edge | — |
| CompetitorPitted | Opponents | rival ±1 **transición** in_pits | ✅ edge | cold start no dispara |
| **GapClosed** | Timings / gaps | gap <1.5s | ✅ edge | — |
| PushNow | `PushNow.cs` | undercut o ≤3 vueltas | ✅ edge | — |
| SessionEnd | SessionEndMessages | fin sesión | ✅ `_fired` | — |
| PhaseChanged | session phase | cambio fase | ✅ edge | — |
| PilotQuestion | free-form vs 100+ cmds | PTT → LLM | ✅ | CC más grammar |

---

## 5. Audio / pipelines (#17–24)

| # | CC | Vantare | Pipeline | CI |
|---|-----|---------|----------|-----|
| 17 | PTT fuel / status | `handle_pilot_question` → `llm_pending` | backend → WS → `advice_*` → TTS NORMAL | ✅ |
| 18 | Interrumpe mensaje anterior | `cancel_current_llm` + `advice_start` → `clearPendingNormalTts` | frontend queue | ✅ `test_preemption` |
| 19 | Spotter durante LLM | IMMEDIATE preempt NORMAL | `priorityAudioQueue` + `useWebSocket` | ✅ integración |
| 20 | Ducking juego | `duck_lmu` @ 0.65 | Tauri Windows | ✅ impl |
| 21 | Spotter off quali | `spotterOffQualifying` | config WS + UI | ✅ |
| 22 | Ack spotter sin voz | property toggle | `NO_VOICE_CATEGORIES` + priority 1 | ✅ |
| 23 | Position / lap commentary | `Position`, `LapTimes` | `ProactiveMonitorSuite` → debounce 3s → `commentary_end` → LLM batch | ✅ monitors |
| 24 | Pearls | `PearlsOfWisdom` | `PearlsService` max 2/carrera (normal) | ✅ `test_emit_pearl` |

### Flujos a verificar en revisión

```
LMU → sidecar/strategy_service → backend WS
  ├─ spotter @ 20Hz → alert (IMMEDIATE) → TTS cache → priorityAudioQueue
  ├─ engine @ 0.5Hz → alert | llm_pending/advice_* | commentary_end | pearl
  └─ pilot_question → llm_pending → advice_* (stream)

Frontend: shouldVoiceAlert → enqueueTtsText → processTtsQueue → duck_lmu
```

**Scripts gate (sin LMU):**

```powershell
python scripts/verify_spotter_pipeline.py
python scripts/verify_audio_pipeline.py
python scripts/verify_alpha_parity.py
cd backend; python -m pytest tests/test_fuel_safety.py tests/test_audio_trigger_matrix.py tests/test_preemption.py -q
cd frontend; npm test -- alertVoice.test.ts priorityAudioQueue.test.ts audioPipeline.integration.test.ts --run
```

---

## 6. Commentary proactivo vs CC Events

| event_id | CC módulo | verbosity_min | Cooldown Vantare | Observación |
|----------|-----------|---------------|------------------|-------------|
| position_change | Position | MEDIUM | — | OK; debounced en orchestrator |
| lap_complete | LapTimes | LOW | — | OK |
| gap_update | Timings | MEDIUM | 45s | CC: frecuencia 0–10; Vantare: fijo 45s |
| race_start | Session start | HIGH | once | OK |
| session_end | SessionEndMessages | MEDIUM | once | OK |
| flags_yellow | FlagsMonitor | HIGH | transition | OK en monitors (≠ trigger LLM) |
| penalties | Penalties | HIGH | edge | OK |
| fuel | Fuel | MEDIUM | 90s | ✅ finish-safe (`is_fuel_autonomy_critical`) |
| tyre_monitor / brake_wear | TyreMonitor | MEDIUM | 120s | OK cooldown |
| pit_stops | PitStops | MEDIUM | 90s | OK |
| push_now | PushNow | HIGH | 60s | OK en commentary; trigger LLM aparte |
| opponents | WatchedOpponents | LOW | 45s | OK |
| frozen_order | FrozenOrderMonitor | HIGH | once | OK |
| drs | OvertakingAids | LOW | — | parcial LMU |

**CommentaryOrchestrator:** debounce 3s, max wait 8s, batch LLM (`format_commentary_batch`). CC: mensajes deterministas grabados — **arquitectura distinta**, aceptable para alpha.

**VerbosityController:**

| Nivel | Vantare emite | CC analogía |
|-------|---------------|-------------|
| silent | ≥ CRITICAL | “Keep quiet” (spotter sigue salvo spot off) |
| normal | ≥ MEDIUM | default |
| detailed | ≥ LOW | “Keep me informed” + más lap reports |

**Faltante CC:** `priortise_messages_depending_on_situation` (qualifying lap, presión) — solo tenemos `brakingZonesMute` en frontend para TTS NORMAL.

---

## 7. Perlas vs `PearlsOfWisdom.cs`

| Aspecto | CC | Vantare |
|---------|-----|---------|
| Activación | prop `enable_pearls_of_wisdom` | siempre si verbosity ≠ silent |
| Frecuencia | 0–10 + min time between | max **2** (normal) / **4** (detailed) por carrera |
| Tipos | general encouragement | STANDARD, COMEBACK, FAST_LAP, OVERTAKE |
| Sweary | opcional | `sweary_messages` + pool alternativo |
| Quejas negativas | max complaints/session (60) | no equivalente |

**Paridad:** ⚠️ funcional pero menos configurable. No bloqueante alpha.

---

## 8. Gaps (#10) — diseño intencional vs CC

| | CC | Vantare |
|---|-----|---------|
| Spotter gap <0.5s | audio si `enable_gap_messages` | `alert` WS sí, **TTS no** (`category=gaps`) |
| Timings periódico | frecuencia configurable | `gap_update` commentary cada 45s (voz NORMAL) |
| Trigger `GapClosed` | batalla táctica | LLM edge-once si gap <1.5 | ✅ |

**Recomendación:** mantener spotter gaps UI-only (evita saturar TTS en batalla); opcional flag `enableGapVoice` futuro.

---

## 9. Backlog post-auditoría (orden sugerido)

### P0 — bugs / spam (antes de LMU larga)

1. ~~Aplicar `fuel_critical_from_strategy` en `proactive_monitors._eval_car_monitors`.~~ ✅ Jun 2026
2. ~~Edge-once en `GapClosedTrigger`, `PushNowTrigger`, `CompetitorPittedTrigger`, `TiresThermalOverheatingTrigger`, `TyreDegAccel`, `HybridDeployMap`, `WeatherChange`.~~ ✅ Jun 2026
3. Revisar solapamiento fuel spotter / trigger / commentary en escenario `<3` vueltas pero finish-safe. ⚠️ mitigado en trigger+monitor; spotter `<1` separado

### P1 — paridad CC útil

4. ~~Actualizar `docs/crewchief-comparison.md` §3.1 spotter (❌ → ✅).~~ ✅ Jun 2026
5. Propiedad UI `enableGapMessages` (default false, como CC).
6. `set_verbosity` vía PTT ya existe en LLM tools — documentar frases ES.

### P2 — beta

7. PitManager voz LMU (virtual energy, fuel ration).
8. `prioritize_messages_under_pressure` (quali lap / sectores difíciles).
9. Persistencia `fuel_usage.json` por coche/pista.

---

## 10. Checklist LMU — qué falta marcar en pista

Tras esta auditoría, **CI cubre 14–24**; **LMU manual pendiente** en 1–13 y validación real de 17–20 (ducking, preempt bajo carga).

Usar `.omo/evidence/audio-lmu-validation.md` fila a fila en sesión Spa/Monza/Le Mans.

---

*Generado: Jun 2026 — sesión paridad CC post fuel finish-safe + quali silent.*
