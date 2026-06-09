# First deploy runbook — Vantare Ingeniero v1 desktop

> Runbook para el **primer deploy público** del instalador Windows. Alineado con CI/CD quality gates, ADRs y checklist de lanzamiento.

## Scope del deploy

| In scope | Out of scope (beta) |
|----------|---------------------|
| Instalador NSIS Windows x64 | macOS / Linux |
| GitHub Release + auto-update | Code signing (SmartScreen warning OK) |
| LMU + telemetría nativa | Pit menu write, SDK público |

## Fase 0 — Pre-requisitos (una vez)

- [ ] `LLM_API_KEY` documentado en `.env.example` (sin secretos en repo)
- [ ] Rama `master` recibe CI verde (backend + frontend build)
- [ ] ADRs 001–003 revisados en `docs/decisions/`
- [ ] README raíz actualizado

## Fase 1 — Quality gate (automático)

Disparar o verificar **CI** en la rama que se va a taggear:

```bash
gh workflow run ci.yml --ref crewchief-parity   # o master tras merge
gh run list --workflow=ci.yml --limit 1
```

Debe pasar:

1. **Backend tests** (Windows, coverage ≥ 70 %)
2. **Frontend tests** (Vitest)
3. **Frontend build** (`tsc && vite build && build:electron`)
4. **Smoke import** backend

Opcional manual: **Pre-Release Gate** workflow (build desktop sin publicar).

## Fase 2 — Versión y changelog

1. Alinear versión en:
   - `frontend/package.json`
   - `backend/src/version.py`
   - `backend/pyproject.toml`
2. Entrada en `CHANGELOG.md`
3. Commit: `release(vX.Y.Z): ...`

## Fase 3 — Tag y release

```powershell
git tag -a vX.Y.Z -m "Vantare Ingeniero vX.Y.Z"
git push origin vX.Y.Z
```

Workflow **Release Desktop** publica:

- `frontend/release/vantare-ingeniero-X.Y.Z-setup.exe`
- `frontend/release/latest.yml`

Monitor:

```bash
gh run list --workflow=release-desktop.yml --limit 1
gh run watch <run-id>
```

## Fase 4 — Smoke post-release (manual, 15 min)

Instalar el `.exe` de Releases en máquina limpia (o VM). Checklist: [electron-smoke-checklist.md](../qa/electron-smoke-checklist.md)

**Crítico primer arranque:**

- [ ] Hub visible (no pantalla negra)
- [ ] Backend arranca (indicadores health en header)
- [ ] Overlay toggle funciona
- [ ] Avanzado → Actualizaciones → “Estás en la última versión” o update flow

## Fase 5 — Lanzamiento (comunicación)

### Internal (Phase 1 launch-strategy)

- 2–3 beta testers LMU con Discord/chat directo
- Recoger trace + feedback 48 h

### Alpha pública (Phase 2)

- Publicar Release en GitHub con notas (template `.github/release-template.md`)
- Post en comunidad LMU / sim racing (rented channel → link a Releases = owned)
- Incluir requisitos: Windows, LMU, API key StepFun propia

### Rollback

1. **App:** publicar tag anterior con `git push --force origin vX.Y.Z` (solo emergencia) o tag `vX.Y.Z-1`
2. **Comunicación:** pin Release anterior en GitHub
3. Usuarios con auto-update: panel Actualizaciones tras nuevo tag

## Definition of Done — primer deploy

- [ ] Release GitHub con `.exe` + `latest.yml`
- [ ] Smoke checklist completado en hardware real
- [ ] CHANGELOG + README publicados
- [ ] CI verde en `master`
- [ ] Al menos 1 tester externo confirmó arranque OK

## Referencias

- [Instalación desktop](../instalacion-desktop.md)
- [ADR-002 GitHub Releases](../decisions/ADR-002-github-releases-auto-update.md)
- [Plan desktop auto-update](../superpowers/plans/2026-06-08-desktop-installer-auto-update.md)
