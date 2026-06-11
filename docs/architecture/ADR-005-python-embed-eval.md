# ADR-005: Evaluación python-embed como alternativa PyInstaller

> **Estado:** Borrador — solo evaluación, no implementar en beta.  
> **Contexto:** Hito 7 reveló fragilidad en `build_backend.py` Fase 2 (copia manual `src/` → `_internal/src/`).  
> **ADR relacionados:** ADR-004-R1 (monolito in-process)

## Problema

PyInstaller `--onedir` produce un bundle funcional, pero:

1. **Copia manual de source**: Fase 2 copia `src/`, `shared-telemetry/`, `shared-strategy/` a `_internal/`. Esto es frágil (`spotter_eval_loop` dead code, `enable_commentary_batch` property assign).
2. **Tamaño**: Build actual ~30 MB de backend + ~400 MB total instalador.
3. **Tiempo de build**: PyInstaller + electron-builder > 5 minutos en desarrollo.
4. **Hidden imports**: Lista manual en `build_backend.py` que puede desincronizarse (D7 mitigado por `test_build_hidden_imports.py`).

## Alternativa: python-embed + pip

- Distribuir Python embebido (Windows embeddable package, ~25 MB) + un `pip install -r requirements.txt` en postinstall.
- Source via wheel de proyecto o copia directa.
- No requiere hidden-imports ni Fase 2.
- Electron-builder incluye python-embed como recurso extra.

### Pros

| Aspecto | PyInstaller | python-embed + pip |
|---------|-------------|-------------------|
| Source parity | Fase 2 manual | Natural (pip install .) |
| Hidden imports | Manual list | No needed |
| Build speed | ~3-5 min | ~30s + pip download |
| Bundle size | ~30 MB backend | ~25 MB embed + ~100 MB site-packages |
| Dead code risk | Bytes desincronizados | Source siempre actual |

### Contras

| Aspecto | Impacto |
|---------|---------|
| Startup latency | python-embed carga módulos desde archivos (vs PyInstaller CArchive) |
| pip disponible | CI/end-user necesita acceso a PyPI o vendored wheels |
| Path resolution | `sys._MEIPASS` PyInstaller no funciona; requiere setup `PYTHONPATH` |
| DLLs nativos | PyInstaller resuelve automáticamente; python-embed requiere empaquetar manual |
| pygame/wheels nativos | Python embed puede no encontrar DLLs sin vc_redist |

## Criterios de migración (gate)

No implementar en beta. Evaluar post-beta si:

1. **Bundle size supera 500 MB** total installer.
2. **Build time CI > 10 minutos**.
3. **Hidden import drift causa bug en pista** (D7 recurrente).
4. **Fase 2 manual falla** en release (source no copiada → ImportError).

## Conclusión

| Decisión | Timeline |
|----------|----------|
| ❌ No migrar en beta | Beta estable con PyInstaller + gates (Hito 7) |
| ⏳ Evaluar post-beta | Si criterios arriba se alcanzan |
| 🔧 Mantener gates | `verify_bundled_main`, `bundle_freshness`, `test_build_hidden_imports` |

> Ver también: `docs/superpowers/plans/2026-06-07-voice-beta-hito-07-bundle-release.md` — gates actuales.
