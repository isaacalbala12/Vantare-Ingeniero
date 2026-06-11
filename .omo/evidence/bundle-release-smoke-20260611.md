# Bundle Release Smoke — 2026-06-11

## Automatizado
| Check | Resultado | Output |
|-------|-----------|--------|
| verify_bundled_main (build) | PASS | `[+] Bundle main.py contract OK` |
| verify_bundle_startup.ps1 | PASS | player=PygameAudioPlayer ticks=200 |
| verify-release.ps1 | PASS | ALL GATES PASSED |

## Revisión orquestador (2026-06-11)

| Check | Verdict |
|-------|---------|
| GATE automatizado | ✅ Re-ejecutado: verify_bundle_startup exit 0, ticks=208 |
| Bundle main.py | ✅ `set_enable_commentary_batch(False)` presente |
| spotter_eval_loop | ✅ ausente en bundle |
| setup.exe 0.2.13 | ✅ coherente con package.json |
| INDEX Hito 7 | ✅ marcado Completo |
| Manual pre-pista | ⏳ pendiente usuario (audio Config, doctor -WithDoctor) |

## Manual (obligatorio pre-pista)
- [ ] Abrir `frontend/release/win-unpacked/Vantare Ingeniero IA.exe`
- [ ] Config → «Probar audio (backend)» audible
- [ ] `/health` desde bundle: backend_playback=true
- [x] Spotter proximity sin doble TTS frontend — validado piloto jun 2026

## doctor.ps1
```powershell
powershell -File scripts/doctor.ps1 -WithDoctor
```
(requiere backend en :8008 — pendiente hasta pista)

## Deuda conocida
- duck_lmu.exe: WARN si ausente (Hito 8) — confirmado durante build: `file source doesn't exist ... duck_lmu.exe`
- Fase 2-R1 ProcessPool: gated post-métricas p95

## Trace-the-flag (2026-06-11)
- `verify_bundled_main|verify_bundle_startup|bundle_main_contract|set_enable_commentary_batch`: todos cableados en build_backend.py, verify_bundle_startup.ps1, verify-release.ps1, doctor.ps1
- `spotter_eval_loop`: ZERO matches en backend/src, backend/dist, frontend/release
- `enable_commentary_batch = False`: solo en verbosity_controller.py (backing field del setter) — legítimo

## Arquitectura
- PyInstaller `--onedir` + Fase 2 copia `src/` → `_internal/src/`
- Gates en build, doctor, verify-release, verify_bundle_startup dedicado
- Invariantes I1–I7 cubiertas
