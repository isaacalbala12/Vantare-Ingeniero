# Beta Release — Vantare Ingeniero IA

## TL;DR

> **Quick Summary**: Preparar la primera release beta de Vantare Ingeniero IA con LLM proxy via Cloudflare Worker + license keys + paridad de eventos CrewChiefV4 + deuda técnica solucionada.
>
> **Deliverables**:
> - Cloudflare Worker proxy a Stepfun API con validación de license key + logging
> - `src/auth/` package con license_provider + estructura preparada para Google OAuth
> - Admin script `gen_keys.py` para generar claves alfanuméricas
> - Frontend: campo de license key en ConfigTab + pantalla de first-run
> - 4 clusters de bugs reales solucionados (10 tests FAIL → PASS)
> - 7 nuevos eventos CrewChief: DriverSwaps, RaceTime, Penalties, MulticlassWarnings, OvertakingAids, Opponents, Timings
> - Bug 6 arreglado: `rain_intensity` en conditions_monitor
> - Documento de vision: motor Monte Carlo para estrategia (post-beta)
> - PyInstaller + Tauri bundle con licencia validada
>
> **Estimated Effort**: LARGE (3+ meses de beta)
> **Parallel Execution**: YES — Waves 1+2 paralelos, luego Wave 3, luego Wave FINAL
> **Critical Path**: Worker deploy → Auth integrado → Bugs fix → Eventos nuevos → Release

---

## Context

### Original Request
Preparar release beta con 4 bloques: (1) LLM proxy con Stepfun + license keys, (2) Paridad completa de eventos CrewChiefV4 + documento Monte Carlo, (3) Deuda técnica y calidad, (4) Release beta.

### Investigaciones Realizadas

**CrewChiefV4 repo analysis**: 682 archivos C#, 44 clases de evento, ~64,000 sonidos. Spotter cartesiano, eventos por polling (10-60Hz), sistema de audio con PlaybackModerator (prioridad/verbosidad). Sin Monte Carlo — todo determinista.

**[EN PROGRESO] Full feature audit**: El análisis inicial solo cubrió eventos. Hay muchas más features en CrewChiefV4 (audio prioritization, pit manager por voz, comandos de voz, overlays, packs de sonido, configuración avanzada). Un subagente `deep` está haciendo un audit completo feature-por-feature. Los resultados actualizarán el alcance de Wave 3.

**10 test failures classified**: 10/10 son REAL BUGS en 4 clusters:
- **Cluster A**: `game_state_builder.py` no mapea campos críticos (overheating, track_definition, pit_state, tyre_compound)
- **Cluster B**: `conditions_monitor.py` sin guard `None` en `weather`
- **Cluster C**: Secuencias duplicadas en eventos (flags_monitor=position, fuel=position, lap_counter=tyre_monitor)
- **Cluster D**: FCY flags_monitor manda a cola normal en vez de inmediata

**Bug 6**: `'NoneType' object has no attribute 'rain_intensity'` — production crash en conditions_monitor

### Metis Review
**Gaps identificados**:
- Workers.dev subdominio gratuito — no necesita dominio propio
- Stepfun es OpenAI-compatible — cambio de config, no de código
- Las license keys son para TRACKING, no anti-piracy
- HMAC signing diferido para v1.0 (pago)
- Scope "todos los eventos de CrewChief" es 6-12 meses sin acotar — definimos 7 eventos para beta
- rate limiting: 60 req/min/key default configurable

---

## Work Objectives

### Core Objective
Release beta funcional con LLM, autenticación por license key, paridad de eventos críticos con CrewChiefV4, y cero bugs conocidos en la suite de tests.

### Concrete Deliverables
- Worker Cloudflare desplegado en `*.workers.dev`
- `backend/src/auth/` con `protocol.py`, `license_provider.py`, `google_provider.py` (stub), `database.py`, `models.py`
- Script `scripts/gen_keys.py` para generar claves `VNT-BETA-XXXX-XXXX`
- ConfigTab con campo de license key + first-run flow
- `game_state_builder.py` con todos los mapeos de campos faltantes
- `conditions_monitor.py` con guard `None` en weather
- Secuencias de eventos únicas
- FCY flags_monitor con `play_imm()` + pausa de cola
- 7 nuevos eventos CrewChief: DriverSwaps, RaceTime, Penalties, MulticlassWarnings, OvertakingAids, Opponents, Timings
- Documento de visión: `docs/strategy/MONTE-CARLO-ENGINE.md` (post-beta, no bloqueante)
- PyInstaller spec actualizado con auth
- Tauri bundle con Worker URL
- Scripts de install en Windows + Linux

### Definition of Done
- [ ] Worker acepta key válida y proxea a Stepfun → 200 + streaming
- [ ] Worker rechaza key inválida/faltante → 401
- [ ] Admin script genera 10 keys válidas
- [ ] Frontend permite ingresar key en first-run
- [ ] `pytest tests/ -v` → 0 failures (o solo los pre-existentes documentados)
- [ ] `npx vitest run` → 88/88 pass
- [ ] `npx playwright test` → 3/3 pass
- [ ] `npx tsc --noEmit` → 0 errors
- [ ] PyInstaller bundle arranca con key válida
- [ ] Tauri build instalable en Windows + Linux

### Must Have
- Worker proxy con logging estructurado (JSON a stdout)
- License key con checksum (catch typos client-side)
- First-run flow obligatorio (sin key no se puede usar la app)
- Todos los 10 bugs tests solucionados
- 7 nuevos eventos con sus tests E2E
- Google OAuth stub listo para el futuro

### Must NOT Have (Guardrails)
- NO implementar Google OAuth (solo stub)
- NO portal admin web
- NO per-user token quotas
- NO modificar `src/intelligence/events/` existentes (solo añadir nuevos)
- NO multi-idioma (solo inglés para beta)
- NO auto-updater
- NO telemetry SDK
- NO macOS installer
- NO `allow_origins=["*"]` en CORS
- NO `print()` en código de producción

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: SI
- **Automated tests**: Tests-after (primero implementar, luego testear)
- **Framework**: pytest + vitest + Playwright + wrangler test

### QA Policy
Cada tarea incluye QA scenarios con tool específico, pasos concretos, aserciones exactas, y evidencia.

**Filosofía de testing** (heredero de pipeline-review):
- **Tests E2E de pipeline, no de archivos.** Cada test debe verificar que el workflow completo funciona (evento → engine → broadcast → UI), no que un método existe o que un archivo está bien formado.
- **Componentes reales, no mocks.** `unittest.mock` prohibido para: CrewChiefRuntime, EventEngine, FrameCache, AudioPlayer, SpotterService, NoisyCartesianCoordinateSpotter. Usar `TestClient` real, `WebSocket` real.
- **Cada nuevo evento → test E2E** como `test_crewchief_event_flow_e2e.py` (inyectar TelemetryFrame → verificar mensaje en broadcast).
- **Cada bug fix → test que lo atrapa** queda en la suite como garantía de no-regresión.
- **Tests existentes se revisan y mantienen** — si un test se vuelve obsoleto por cambio de API, se actualiza, no se borra.

**Herramientas por tipo**:
- **Auth E2E**: `pytest tests/test_auth_e2e.py -v` (frontend → backend → Worker → Stepfun mock, full flow)
- **Worker**: `wrangler test` + `curl`
- **Backend bugs**: `pytest tests/test_crewchief_pipeline.py tests/test_crewchief_integration.py -v`
- **Nuevos eventos**: `pytest tests/test_<evento>_e2e.py -v` (sigue patrón de `test_crewchief_event_flow_e2e.py`)
- **Frontend**: `npx vitest run` + `npx playwright test`
- **TypeScript**: `npx tsc --noEmit`
- **Bundle**: `npx tauri build` + install en VM limpia

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (LLM Proxy + Auth infrastructure — 100% paralelo):
├── Task 1: Deploy Cloudflare Worker proxy
├── Task 2: Create src/auth/ package
├── Task 3: Admin script gen_keys.py
├── Task 4: Frontend license key UI (ConfigTab + first-run)
└── Task 5: Integrate auth + proxy in backend

Wave 2 (Bug fixes — paralelo entre sí, independiente de Wave 1):
├── Task 6: Fix Cluster A — game_state_builder.py field mappings
├── Task 7: Fix Cluster B — conditions_monitor weather None guard
├── Task 8: Fix Cluster C — duplicate event sequences
├── Task 9: Fix Cluster D — FCY queue routing
└── Task 10: Verify all 10 tests pass

Wave 3 (CrewChief parity — 11 tareas, 4 fases):
├── Fase 3A (Audio Quality of Life — CRÍTICO):
│   ├── Task 11: Threshold interrupción configurable (ya existe flag)
│   ├── Task 12: Cablear expiración mensajes (ya existe campo)
│   ├── Task 13: Auto-verbosidad por tráfico
│   └── Task 14: Expandir configuración + persistencia (~20-25 settings)
├── Fase 3B (Spotter Polish — IMPORTANTE):
│   ├── Task 15: Filtro velocidad + debounce
│   └── Task 16: Repetición "still there" + FCY
├── Fase 3C (Nuevos Eventos — IMPORTANTE):
│   ├── Task 17: DriverSwaps + RaceTime + Penalties
│   └── Task 18: MulticlassWarnings + OvertakingAids + Opponents + Timings
└── Fase 3D (Tests + Mantenimiento):
    ├── Task 19: Tests E2E para nuevas features
    ├── Task 20: Revisar tests existentes
    └── Task 21: Integration verification full suite

Wave FINAL (Release prep):
├── Task F1: PyInstaller spec update + bundle test
├── Task F2: Tauri build + VM install test
├── Task F3: Beta documentation (README-BETA.md)
├── Task F4: Plan Compliance Audit (oracle)
└── Task F5: Code Quality Review
```

---

## TODOs

> Task labels use bare numbers. Final Wave uses F-prefix.

- [x] 1. Deploy Cloudflare Worker proxy a Stepfun — `build`
- [x] 2. Create `src/auth/` package — `build`
- [x] 3. Admin script `scripts/gen_keys.py` — `build`
- [x] 4. Frontend license key UI — `build`
- [x] 5. Integrate auth + proxy in backend — `build`
- [x] 6. Fix Cluster A — `game_state_builder.py` field mappings — `deep`
- [x] 7. Fix Cluster B — `conditions_monitor.py` weather None guard — `deep`
- [x] 8. Fix Cluster C — duplicate event sequences — `deep`
- [x] 9. Fix Cluster D — FCY queue routing — `deep`
- [x] 10. Verify all 10 tests pass — `build`
- [x] 11. Threshold de interrupción configurable — `unspecified-low`
- [x] 12. Cablear expiración de mensajes en player loop — `unspecified-low`
- [x] 13. Auto-verbosidad por tráfico — `unspecified-low`
- [x] 14. Expandir configuración y persistencia — `visual-engineering`
- [x] 15. Spotter: filtro de velocidad de rivales + debounce — `unspecified-low`
- [x] 16. Spotter: repetición "still there" + manejo FCY — `unspecified-low`
- [x] 17. DriverSwaps, RaceTime, Penalties events — `deep`
- [x] 18. MulticlassWarnings + OvertakingAids + Opponents + Timings events — `deep`
- [ ] 19. Tests E2E para todas las nuevas features — `unspecified-high`
- [ ] 20. Revisar y mantener tests existentes — `unspecified-high`
- [ ] 21. Integration verification — full suite — `build`

  **What to do**: `pytest tests/ -v`, `npx vitest run`, `npx playwright test`, `npx tsc --noEmit`. Todo debe pasar.
  **Evidence**: `.omo/evidence/beta/full-suite.txt`

---

### Post-Beta: Monte Carlo Vision Document (no bloqueante)

Este documento se crea como side-task, no bloquea la release. No tiene checkbox porque no está en el camino crítico de la beta.

**Monte Carlo strategy engine — vision document**
  **What to do**:
  1. Crear `docs/strategy/MONTE-CARLO-ENGINE.md`
  2. Documento de VISIÓN, no de implementación. Contenido:
     - Qué problema resuelve (CrewChief es determinista, nosotros podemos simular)
     - Arquitectura conceptual (simulación de N carreras con variaciones)
     - Inputs: consumo de combustible, desgaste de neumáticos, ventanas de pit, tráfico
     - Outputs: ventana de pit óptima, estrategia de combustible, riesgos
     - Dependencias con modelos de datos existentes
     - Priorización tentativa para fase post-beta
  3. **NO bloquea la release**. Es un documento para el futuro.
  
  **Must NOT do**:
  - NO implementar el motor
  - NO ponerlo en el roadmap obligatorio de la beta
  
  **Parallelization**: Puede hacerse en cualquier momento (Wave 3 o post-Wave 3)
  
  **Acceptance Criteria**:
  - [ ] `docs/strategy/MONTE-CARLO-ENGINE.md` existe
  - [ ] Describe arquitectura conceptual, inputs, outputs
  - [ ] Incluye comparación con CrewChiefV4 (determinista)
  - [ ] No condiciona la release

  **Commit**: NO (se commiteará cuando se implemente, o como doc separado)
  **Evidence**: `docs/strategy/MONTE-CARLO-ENGINE.md`

---

## Final Verification Wave

- [ ] F1. **PyInstaller spec update + bundle test** — `quick`
  Actualizar `backend.spec` para incluir `src/auth/`. Build: `pyinstaller backend.spec`. Verificar que el binario arranca y valida license key.
  Output: `Bundle [OK/FAIL] | Auth [OK/FAIL]`

- [ ] F2. **Tauri build + VM install test** — `unspecified-high`
  `npx tauri build`. Instalar en Windows VM limpia (sin Python/Node). Verificar first-run flow, license key entry, LLM funciona.
  Output: `Tauri [OK/FAIL] | VM test [OK/FAIL]`

- [ ] F3. **Beta documentation** — `writing`
  Crear `README-BETA.md` con: cómo obtener key, qué hace la key, canal de feedback, qué hacer si la app falla.
  Output: `README-BETA.md [CREATED]`

- [ ] F4. **Plan Compliance Audit** — `oracle`
  Verificar: todos los Must Have implementados, ninguno de los Must NOT violado, commits correctos.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Scope [contained] | VERDICT`

- [ ] F5. **Code Quality Review** — `unspecified-high`
  `pytest tests/ -v`, `vitest run`, `tsc --noEmit`. Check anti-patterns.
  Output: `Build | Lint | Tests | VERDICT`

---

## Commit Strategy

- **Commit 1** (Wave 1): `feat(auth): license key system + Cloudflare Worker proxy`
- **Commit 2** (Wave 2): `fix(pipeline): resolve 4 bug clusters — 10 test failures → PASS`
- **Commit 3** (Wave 3): `feat(events): 7 new CrewChief events + CrewChief feature parity`

- **Commit 4** (Wave FINAL): `chore(release): beta packaging + installers`

---

## Success Criteria

### Verification Commands
```bash
# Worker
curl -X POST https://vantare-llm-proxy.workers.dev/v1/chat/completions ...

# Backend bugs
pytest tests/test_crewchief_pipeline.py tests/test_crewchief_integration.py -v

# Full E2E
pytest tests/test_crewchief_event_flow_e2e.py tests/test_frame_cache_flow_e2e.py -v

# Frontend
npx vitest run
npx playwright test

# TypeScript
npx tsc --noEmit

# Build
pyinstaller backend.spec
npx tauri build
```

### Final Checklist
- [ ] Worker deployed and tested
- [ ] License keys generated and distributed
- [ ] All 10 test failures fixed
- [ ] All 7 new events implemented + tested
- [ ] Monte Carlo design doc created
- [ ] Beta installers building
- [ ] README-BETA.md written
- [ ] F1-F5 all approved
