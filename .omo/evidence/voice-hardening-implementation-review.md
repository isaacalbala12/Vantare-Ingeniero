# Voice Pipeline Hardening — Implementation Review

**Fecha:** 2026-06-10  
**Revisor:** sesión de adecuación post-implementación  
**Veredicto:** **REQUEST_CHANGES menor** — base sólida, audit inflado, 1 gap de producción

---

## Resumen vs auditoría del otro modelo

| Claim del otro modelo | Realidad verificada |
|----------------------|---------------------|
| 50 frontend + 5 backend = 55 tests | **45 frontend + 5 backend = 50** (`verify_voice_contract.py` ejecutado) |
| Task 6.5 “refactor separado” | Correcto — **`useWebSocket.ts` sigue con cola TTS propia**; `ttsPipeline.ts` no está en producción |
| Code reviews hechos | No — correctamente marcados como proceso |
| Commits hechos | No |
| Todo corregido | **No** — ver hallazgos P1/P2 |

---

## Findings (code-review-expert)

### P1 — High

1. **Task 6.5 no integrado — watchdog no protege desktop**
   - `ttsPipeline.ts` existe y tiene tests, pero `useWebSocket.ts` mantiene `enqueueTtsText` / `processTtsQueue` duplicados (~L185–403).
   - El watchdog VC-Q07 **no aplica** al binario que usa el piloto hasta completar 6.5.

2. **VC-B05 estaba mal implementado** (corregido en esta review)
   - Test original llamaba `_emit_voice_response` — duplicaba VC-B02, no probaba spotter.
   - **Fix:** `SpotterService` + fixture `world_overlap_no_path_delta`.

3. **VC-B04 demasiado débil**
   - Solo verifica que `evaluate_cycle` no crashea; no asserta emisión de alerta fuel.
   - Riesgo: regresión backend pasa CI sin detectar.

### P2 — Medium

4. **`verify_audio_pipeline.py` no incluía voice gate** (corregido)
   - Plan Task 10 pedía wiring; faltaba. Añadido paso `[0/4]`.

5. **`ttsPipeline` cache path dejaba cola sin shift + processing colgado** (corregido)
   - En cache hit no hacía `queue.shift()` ni `finish()` → watchdog a 30s.
   - Añadido `deferFinishUntilPlaybackIdle` (default `false` en tests; `true` al integrar con `audioQueue.onIdle`).

6. **`shouldVoiceAlert` aún en `useWebSocket`**
   - L827: historial radio. No bloquea TTS, pero viola DoD “solo ttsPlaybackGate”.

7. **VC-P06/P07 duplicados en fixtures** (corregido)
   - Filas en `voiceContractCases.ts` confundían P07 (playback discard) con allow gate.

8. **VC-R02 smoke incompleto**
   - `--inject-alert` existe pero no asserta evaluación cliente; solo POST 200.

### P3 — Low

9. **`evaluateAlertTts` no registra denies** — solo `logTtsBlocked` desde hook (OK en runtime).
10. **`TtsDiagnosticsPanel`** — no implementado (opcional).
11. **Task 14 POST /tts em-dash** — pendiente follow-up.

---

## Lo que sí está bien hecho

- Puerta unificada `evaluateAlertTts` / `evaluateAdviceTts` / `evaluateCommentaryTts` ✅
- Matriz VC-A01–A17 alineada con contrato (I2, I3) ✅
- `speakOnly` ya no silencia spotter ✅
- `verify_voice_contract.py` + `verify-release.ps1` §1b ✅
- `configMigration.voice.test.ts` VC-R04 ✅
- `debug/inject_alert` + smoke flag ✅
- `ttsDiagnostics` integrado ✅

---

## Estado corregido de tasks

| Task | Estado real |
|------|-------------|
| 0.1–0.2 | ✅ Gates ejecutables |
| 0.3, 0.4, 4.3, 13.2 | ❌ Proceso (review / commit) |
| 1–5, 7–12 | ✅ Código |
| 6.5 | ❌ **Pendiente — prioridad #1 next session** |
| 13.1 | ✅ 50 tests voice contract |
| 13.3 | ✅ Changelog |

---

## Próxima sesión (orden recomendado)

1. **Task 6.5** — Wire `createTtsPipeline` en `useWebSocket` con `deferFinishUntilPlaybackIdle: true` + `audioQueue.setOnIdle`.
2. **Fortalecer VC-B04** — assert categoría `fuel` emitida con engineer ON + speakOnly OFF.
3. **Añadir VC-Q02, Q05–Q06** en `ttsQueue.contract.test.ts`.
4. **Ejecutar** `python scripts/verify_audio_pipeline.py` completo.
5. **Commit** atómico: `feat: voice contract gates + CI` (sin `.env`, sin chroma_db).

---

## Overall assessment

**REQUEST_CHANGES** — mergeable para valor de CI/contrato; **no** considerar el hardening “completo” hasta Task 6.5.
