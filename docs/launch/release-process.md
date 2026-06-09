# Release process (desktop)

## Flujo estándar

```
PR → CI verde → merge master → bump version → tag v* → Release Desktop → smoke → announce
```

## 1. Merge a producción

La rama de integración actual es `crewchief-parity`. Antes del deploy público:

```bash
gh pr create --base master --head crewchief-parity --title "Release vX.Y.Z desktop"
# Tras review + CI
gh pr merge
```

## 2. Tag (sustituir release rota)

Si el tag ya existe y hay hotfix:

```bash
git tag -fa vX.Y.Z -m "Vantare Ingeniero vX.Y.Z"
git push --force origin vX.Y.Z
```

GitHub Release se actualiza con los nuevos artefactos.

## 3. Notas de release

Editar en GitHub o usar template `.github/release-template.md`.

Campos mínimos:

- Requisitos (Windows 10+, LMU, LLM API key)
- SmartScreen / unsigned warning
- Link instalador
- Cambios desde versión anterior (desde CHANGELOG)

## 4. Verificación artefactos

Tras CI release, comprobar:

```powershell
# Descargar release localmente
gh release download vX.Y.Z --dir ./release-verify
Get-ChildItem ./release-verify
```

Debe existir `.exe` y `latest.yml`.

## 5. Post-release

- Ejecutar smoke checklist (`docs/qa/electron-smoke-checklist.md`)
- Monitorear issues GitHub 72 h
- No taggear de nuevo hasta smoke OK
