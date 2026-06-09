# Native telemetry smoke (Task 49)

## S3b gate

- [x] Date: 2026-06-08
- [x] `pytest tests/test_telemetry_frame_builder.py tests/test_lmu_feedback_fixes.py tests/test_strategy_service.py tests/test_penalty_wave1.py tests/test_fcy_wave1.py tests/test_spotter_cc_parity.py -v` PASS (53 tests)

## Automated pre-check
- [x] `python -m pytest tests/test_native_telemetry.py tests/test_native_telemetry_frame_source.py tests/test_telemetry_frame_builder.py tests/test_flags_monitor.py -v` PASS (2026-06-08, 20 tests)
- [x] `python -m pytest tests/test_no_sidecar_endpoint.py -v` PASS (2026-06-08, Task 49-S9)

## Health (native only)
- [x] `(Invoke-RestMethod http://127.0.0.1:8008/health).telemetry.source` = `native` (2026-06-08)
- [x] `shared_memory.status` = `connected` (LMU in session, 2026-06-08)
- [x] No `sidecar` key in `/health` response (2026-06-08, post-S9)

## Sidecar vs native A/B
- [x] **Skipped** — sidecar package removed Task 49-S9; native is sole path

## UI + audio (15 min pista)
- [x] Telemetría viva: vel, vuelta, posición — validado 2026-06-08
- [x] Spotter proximidad audible — validado en pista 2026-06-08
- [x] Banderas amarillas / FCY (módulo flags) — validado 2026-06-08
- [x] Penalización audible (num_penalties en frame) — validado 2026-06-08
- [x] PTT "cállate" → silencio total; respuesta PTT OK — validado 2026-06-08
- [x] Daño / lluvia — validado cuando escenario disponible 2026-06-08

## Task 14 revalidation
- [x] Re-run `.omo/evidence/cc-parity-validation-checklist.md` on native 2-process stack (2026-06-08)
- [x] Update `cc-behavior-parity-matrix.yaml` validation_closure + validation_closure_wave7 (Task 48)

## Task 49 closure (S9)
- [x] Delete `sidecar/` source + bundled `frontend/src-tauri/binaries/sidecar/` (2026-06-08)
- [x] Remove `/ws/sidecar`, `latest_strategy_frame`, health `sidecar` block
- [x] Guard tests: `test_no_sidecar_endpoint.py`
- [x] Tauri: native-only spawn (`VANTARE_NATIVE_TELEMETRY=1`), no sidecar resource in bundle
- [ ] Tauri **release** build smoke — manual: `python backend/build.py`, `npm run tauri build`, verify 2-process (backend.exe + app)
