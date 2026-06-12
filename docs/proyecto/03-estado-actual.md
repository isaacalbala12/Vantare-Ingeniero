# 03 — Estado actual (releases)

> Actualizar este documento tras cada tag release.

**Versión estable publicada:** **v0.5.1** (2026-06-11)  
**Release:** https://github.com/isaacalbala12/Vantare-Ingeniero/releases/tag/v0.5.1  
**Rama integración:** `master`

---

## Historial de versiones (resumen)

| Versión | Fecha | Hito |
|---------|-------|------|
| **0.2.14** | 2026-06-11 | Voice Beta estable — audio backend, race loop monolito, contrato voz |
| **0.3.0** | 2026-06-11 | Frases humanas + Gemini TTS por rol |
| **0.4.0** | 2026-06-07 | Frases editables (PhraseStore, REST `/phrases`, Hub editor) |
| **0.5.0** | 2026-06-11 | Personalidades avanzadas (proactividad, perlas, preview tono) |
| **0.5.1** | 2026-06-11 | Fix auto-update sin firma Authenticode |

Detalle línea a línea: [`../../CHANGELOG.md`](../../CHANGELOG.md).

---

## Gates roadmap 1.0 (registro)

| Versión | GATE | Fecha | Notas |
|---------|------|-------|-------|
| 0.2.14 | ✅ | 2026-06-11 | Voice Beta stable LMU |
| 0.3 | ✅ | 2026-06-11 | Frases + Gemini; tag v0.3.0 |
| 0.4 | ✅ | 2026-06-07 | QA manual usuario OK; incluido en release 0.5.0 |
| 0.5 | ✅ | 2026-06-11 | Personalities + tests; tag v0.5.0 |
| 0.5.1 | ✅ | 2026-06-11 | Updater fix; manual install desde 0.2.x una vez |
| **0.6** | ⏳ | — | **Siguiente** — Inglés |
| 0.7 | ⏳ | — | Comandos ingeniero (tools PTT) |
| 0.8 | ⏳ | — | Pit Manager LMU (REST write) |
| 0.9 | ⏳ | — | Hardening multi-circuito |
| 1.0 | ⏳ | — | Clonación voz |
| 1.1 | ⏳ | — | iRacing + Suite Go |

Mini-plan activo siguiente: [`../superpowers/plans/2026-06-11-roadmap-v06-english.md`](../superpowers/plans/2026-06-11-roadmap-v06-english.md).

---

## Funcionalidades entregadas (checklist producto)

### Voz y audio ✅
- [x] Pipeline voz in-process (pygame, cola, moderador)
- [x] Spotter cartesiano ES
- [x] Edge TTS + Gemini TTS selectable por rol
- [x] Caché frases spotter (warm + invalidate)
- [x] Overlay sincronizado playback WS
- [x] Auto-update GitHub (v0.5.1+ sin firma)

### CrewChief parity (LMU) — parcial ✅
- [x] Módulos CC portados (~25): fuel, flags, lap times, damage, rain, FCY, pits, pearls, …
- [x] Triggers proactivos IntelligenceEngine
- [x] Frases picker con variantes por perfil
- [ ] Pit Manager write (v0.8)
- [ ] Comandos consulta PTT deterministas (v0.7)
- [ ] Validación ≥3 circuitos evidencia (v0.9)

### Personalización ✅
- [x] Perfiles formal / standard / aggressive
- [x] Sweary (lenguaje paddock)
- [x] Proactividad baja/normal/alta
- [x] Frecuencia perlas 0–100%
- [x] Editor frases + export/import JSON
- [ ] Idioma inglés (v0.6)

### Desktop ✅
- [x] Instalador NSIS Windows x64
- [x] Hub configuración completa
- [x] Electron shell
- [ ] Certificado firma código (opcional futuro)
- [ ] `duck_lmu.exe` en bundle (v0.9)

---

## Deuda técnica conocida

| Área | Issue | Prioridad |
|------|-------|-----------|
| `AGENTS.md` | Menciona Tauri/frontend TTS; desactualizado vs Voice Beta | Doc |
| `voice-contract.md` | Diagrama aún muestra TTS HTTP frontend; audio real en backend | Doc / alinear tests |
| Firma código | SmartScreen + updater requieren workaround | v0.9 / infra |
| `duck_lmu` | No incluido en build local si falta cargo release | v0.9 |
| PyInstaller bundle | ~400 MB, warnings opentelemetry/chromadb | v0.9 hardening |
| Evidencia pista | `.omo/evidence/` — validación multi-circuito incompleta | v0.9 |

Planes de hardening: [`../superpowers/plans/2026-06-09-backend-hardening-deuda-tecnica.md`](../superpowers/plans/2026-06-09-backend-hardening-deuda-tecnica.md).

---

## Tests (baseline esperado)

```powershell
# Backend — suite completa (puede tardar)
cd backend
python -m pytest tests/ -q

# Backend — regression voice/spotter
python -m pytest tests/test_spotter.py tests/test_voice_loop.py tests/test_main_lifecycle_contract.py -q

# Frontend
cd frontend
npm test
```

Contrato voz: `python scripts/verify_voice_contract.py` (desde raíz).

---

## Archivos de versión (bump obligatorio en releases)

| Archivo | Campo |
|---------|-------|
| `backend/src/version.py` | `APP_VERSION` |
| `frontend/package.json` | `version` |
| `CHANGELOG.md` | Entrada nueva |
| `frontend/src-tauri/binaries/.../version.py` | Copiado en build |

Tag formato: `vX.Y.Z` → dispara [`release-desktop.yml`](../../.github/workflows/release-desktop.yml).
