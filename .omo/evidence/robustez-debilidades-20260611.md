# Robustez — Matriz debilidades D1–D12

**Fecha:** 2026-06-11  
**Hito:** 8 — Revisión robustez  
**Pre-requisito:** Hito 7 GATE ✅

## V1 pista

**PASS — validado por piloto jun 2026.** Funcionamiento correcto en pista:
- Spotter audible con UI cerrada ✅
- Ingeniero vía PTT + LLM ✅
- Audio backend (pygame) ✅

## Matriz D1–D12

| # | Debilidad | Severidad | Mitigación | Test / Gate | Estado |
|---|-----------|-----------|------------|-------------|--------|
| D1 | Property assign crashea lifespan | P0 | `test_property_assign_guard.py` escanea `main.py`, `engine.py`, `websocket.py` por `.enable_commentary_batch =` | `test_property_assign_guard.py` | PASS |
| D2 | Bundle src ≠ bytecode / copia stale | P0 | `bundle_freshness` en `verify-release.ps1`: mtime de `main.py`, `voice/bridge.py`, `race/tick_loop.py` | `verify-release.ps1` — `bundle_freshness` | PASS |
| D3 | BETA_SLIM bypass vía config WS | P1 | `engine.py:638` — `apply_runtime_config` ignora `enableCommentaryBatch` si BETA_SLIM | `test_config_sync_ws.py::test_config_update_cannot_enable_commentary_batch_when_beta_slim`, `test_beta_slim.py::test_main_slim_uses_commentary_batch_setter` | PASS |
| D4 | VoiceBridge sin event loop pierde audio | P1 | `bridge.py` fallback `asyncio.run(self._enqueue_alert(...))` + log debug | `test_voice_bridge_sync_context.py` — ThreadPoolExecutor desde sync | PASS |
| D5 | V5 test no representa PTT real | P1 | `test_acceptance_v2_v5.py::test_v5_pilot_question_does_not_block_race_tick` con mock LLM lento + asyncio.create_task | p95 inter-tick < 500ms | PASS |
| D6 | duck_lmu missing en release | P2 | `scripts/build-duck-lmu.ps1` documentado; electron-builder WARN aceptable (pycaw fallback) | WARN en build log | WARN |
| D7 | Hidden import drift en módulos nuevos | P2 | `test_build_hidden_imports.py` verifica `build_backend.py` contiene todos los módulos voice/race | `test_build_hidden_imports.py` (lista ampliada a 12 módulos) | PASS |
| D8 | Lifespan wiring solo testeado estático | P1 | `test_lifespan_integration.py` con `TestClient(app)` + `/health` verifica voice+race wiring | `test_lifespan_integration.py` (2 tests: estructura + tick_count avanza) | PASS |
| D9 | `.env` secrets copiados al bundle | P2 | WARN en `build_backend.py` si `OPENAI_API_KEY`/`LLM_API_KEY`/etc tienen valor no vacío | WARN en build (no fail) | WARN |
| D10 | ProcessPool prematuro (GIL) | P3 | Solo doc: gate p95 > 40 ms sostenido en pista | ADR-004-R1 §4.6 | DOC |
| D11 | Dead code confunde rebuild | P2 | `spotter_eval_loop` ausente en `backend/src/` y bundle; `verify_bundled_main()` falla si presente | rg trace-the-flag | PASS |
| D12 | Frontend doble TTS si gate bypass | P1 | `ttsPlaybackGate.ts` — `evaluateAlertTts` retorna `reason: "backend_playback"` cuando `voiceBackendPlayback=true` | VC-A06 matrix (`voiceContractMatrix.test.ts`) | PASS |

## Trace-the-flag final

```powershell
rg "BETA_SLIM|set_enable_commentary_batch|VoiceBridge|voiceBackendPlayback" backend/src frontend/src --glob "*.{py,ts,tsx}" -l
```

Archivos con hits:
- `backend/src/config.py` (BETA_SLIM defaults)
- `backend/src/main.py` (lifespan gates)
- `backend/src/intelligence/engine.py` (runtime gate + setter call)
- `backend/src/intelligence/verbosity_controller.py` (setter)
- `backend/src/services/mqtt_service.py` (BETA_SLIM gate)
- `backend/src/voice/bridge.py` (VoiceBridge)
- `frontend/src/store/config.ts` (voiceBackendPlayback)
- `frontend/src/hooks/useWebSocket.ts` (voiceBackendPlayback + evaluateAlertTts)
- `frontend/src/services/ttsPlaybackGate.ts` (evaluateAlertTts)
- `frontend/src/__tests__/voiceContractMatrix.test.ts` (VC-A06)

```powershell
rg "spotter_eval_loop|\.enable_commentary_batch\s*=\s*False" backend/src backend/dist frontend/release --glob "*.py"
```

Resultado: ZERO matches en `backend/src/` y bundle post-rebuild. ✅

## Deuda post-Hito 8

| Item | Estado | Plan |
|------|--------|------|
| duck_lmu.exe | WARN | `scripts/build-duck-lmu.ps1` — requiere Rust toolchain |
| ProcessPool | DOC | Gate p95 > 40 ms en pista (ADR-004-R1 §4.6) |
| doctor -WithDoctor | Recomendado | Ejecutar cada release con backend en :8008 |

## Revisión orquestador (2026-06-11)

| Check | Verdict |
|-------|---------|
| pytest Hito 8 (17 tests) | ✅ Re-ejecutado localmente |
| verify_beta_gate | ✅ Reportado PASS (1024 back + 277 front) |
| verify-release + bundle_freshness | ✅ Fix rutas bridge/tick_loop aplicado post-review |
| V1 pista | ✅ Piloto confirma jun 2026 |
| INDEX Hito 8 | ✅ marcado Completo |
| D6/D9 WARN | ✅ Aceptable (duck_lmu, .env secrets) |

## DoD Hito 8

- [x] test_lifespan_integration.py green
- [x] bundle_freshness en verify-release (main + bridge + tick_loop)
- [x] build-duck-lmu.ps1
- [x] ADR-005 draft
- [x] evidencia robustez-debilidades-*.md
- [x] verify_beta_gate + verify-release exit 0
- [x] Orquestador marca INDEX ✅
