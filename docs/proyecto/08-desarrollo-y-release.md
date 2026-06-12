# 08 — Desarrollo, build y release

---

## Requisitos dev

| Tool | Versión |
|------|---------|
| Windows 10/11 x64 | Obligatorio (telemetría LMU) |
| Python | 3.12+ |
| Node.js | 22+ |
| Rust | Opcional (`duck_lmu`) |
| Le Mans Ultimate | Para pruebas en pista |

---

## Arranque desarrollo

### Backend

```powershell
cd backend
pip install -e ../shared-telemetry -e ../shared-strategy -e ".[dev]"
copy .env.example .env
# Editar: LLM_API_KEY (obligatorio PTT)
# Opcional: GEMINI_API_KEY
python run_dev.py
```

Health: http://127.0.0.1:8008/health

### Frontend

```powershell
cd frontend
npm ci
npm run dev:electron
```

Hub: http://127.0.0.1:1420 — **arrancar backend aparte** en dev.

Script unificado (si existe): `scripts/dev.ps1`.

---

## Tests

```powershell
# Backend completo
cd backend
python -m pytest tests/ -v

# Regression voice baseline (antes de cada hito)
python -m pytest tests/test_spotter.py tests/test_voice_loop.py tests/test_main_lifecycle_contract.py -q

# Frontend
cd frontend
npm test

# Contrato voz (raíz)
python scripts/verify_voice_contract.py
```

---

## Build instalador

```powershell
# Desde raíz — backend PyInstaller + Electron NSIS
powershell -File scripts/build-desktop.ps1
```

Pasos internos:

1. `backend/build_backend.py` → PyInstaller onedir
2. Copia a `frontend/src-tauri/binaries/backend/`
3. `npm run build:desktop` → `frontend/release/*.exe`

Verificación artefactos: `scripts/verify-desktop-artifacts.ps1`.

---

## Release process

Flujo estándar: [`../launch/release-process.md`](../launch/release-process.md)

```
Código listo → bump version → commit → push master → tag vX.Y.Z → GitHub Release
```

| Paso | Comando / acción |
|------|------------------|
| Bump | `backend/src/version.py`, `frontend/package.json`, `CHANGELOG.md` |
| Commit | Mensaje tipo `chore: release vX.Y.Z …` |
| Push | `git push origin HEAD:refs/heads/master` |
| Tag | `git tag -a vX.Y.Z -m "…"` && `git push origin vX.Y.Z` |
| CI | Workflow `release-desktop.yml` build + upload assets |
| Manual | `gh release create` con `.exe` + `latest.yml` si hace falta |

**Auto-update:** `latest.yml` + `electron-updater`. Desde v0.5.1: sin verificación firma Authenticode.

**SmartScreen:** instaladores unsigned — aviso esperado.

Runbook primer deploy: [`../launch/first-deploy-runbook.md`](../launch/first-deploy-runbook.md).

---

## Variables entorno backend (`.env`)

| Variable | Uso |
|----------|-----|
| `LLM_API_KEY` | PTT / ingeniero (requerido) |
| `LLM_BASE_URL` | API compatible OpenAI |
| `GEMINI_API_KEY` | TTS Gemini opcional |
| `VANTARE_TTS_DEBUG` | Debug bloqueos TTS (I1) |

Nunca commitear `.env`. Ejemplo: `backend/.env.example`.

---

## CI GitHub Actions

| Workflow | Trigger |
|----------|---------|
| `ci.yml` | Push/PR master |
| `release-desktop.yml` | Tag `v*` |
| `pre-release.yml` | Manual smoke gate |

---

## Doctor / diagnóstico

```powershell
powershell -File scripts/doctor.ps1
```

Verifica Python, Node, backend health, paths bundle.

---

## Trabajo con agentes IA

1. **Orquestador** elige versión y revisa gates
2. **Ejecutor** lee mini-plan en `docs/superpowers/plans/2026-06-11-roadmap-vXX-*.md`
3. Implementa tasks en orden con TDD
4. No tocar **Files FORBIDDEN** del mini-plan
5. Al cerrar: pytest + vitest + bump + tag

Prompt continuación: [ORQUESTADOR-PROMPT-CONTINUACION.md](ORQUESTADOR-PROMPT-CONTINUACION.md).

---

## Push git (nota Windows)

Si `git push origin master` falla por tag homónimo:

```powershell
git push origin HEAD:refs/heads/master
```

No commitear: `.env`, `backend/.chroma_db/`, artefactos build locales innecesarios.
