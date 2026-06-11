# Orquestador — Voice Beta Re-architecture

> **Plan maestro (índice):** [`2026-06-07-monolith-voice-beta-rearchitecture.md`](2026-06-07-monolith-voice-beta-rearchitecture.md)  
> **Decisiones:** [`../../architecture/2026-06-07-rearchitecture-decisions-record.md`](../../architecture/2026-06-07-rearchitecture-decisions-record.md)

## ¿Mini-planes o plan principal?

| Rol | Documento |
|-----|-----------|
| **Visión + mapa completo** | Plan maestro (23 tasks) |
| **Ejecución por agente** | **Mini-plan por Hito** (obligatorio) |
| **Revisión entre hitos** | Gate checklist en este INDEX |

**Regla:** Ningún agente implementa un Hito sin leer su mini-plan. El plan maestro no se edita durante ejecución salvo correcciones aprobadas por orquestador.

---

## Mini-planes (uno por fase)

| Hito | Archivo | Estado | Gate previo |
|------|---------|--------|-------------|
| 1 | [`2026-06-07-voice-beta-hito-01-race-loop.md`](2026-06-07-voice-beta-hito-01-race-loop.md) | **Completo** | — |
| 2 | [`2026-06-07-voice-beta-hito-02-voice-inprocess.md`](2026-06-07-voice-beta-hito-02-voice-inprocess.md) | **Completo** | Hito 1 GATE ✅ |
| 3 | [`2026-06-07-voice-beta-hito-03-audio-playback.md`](2026-06-07-voice-beta-hito-03-audio-playback.md) | **Completo** | Hito 2 GATE ✅ |
| 4 | [`2026-06-07-voice-beta-hito-04-frontend-integration.md`](2026-06-07-voice-beta-hito-04-frontend-integration.md) | **Completo** | Hito 3 GATE ✅ |
| 5 | [`2026-06-07-voice-beta-hito-05-slim-doctor.md`](2026-06-07-voice-beta-hito-05-slim-doctor.md) | **Completo** | Hito 4 GATE ✅ |
| 6 | [`2026-06-07-voice-beta-hito-06-beta-gate.md`](2026-06-07-voice-beta-hito-06-beta-gate.md) | **Completo** | Hito 5 GATE ✅ |
| 7 | [`2026-06-07-voice-beta-hito-07-bundle-release.md`](2026-06-07-voice-beta-hito-07-bundle-release.md) | **Completo** | Hito 6 GATE ✅ |
| 8 | [`2026-06-07-voice-beta-hito-08-robustez-debilidades.md`](2026-06-07-voice-beta-hito-08-robustez-debilidades.md) | **Completo** | Hito 7 GATE ✅ |

---

## Protocolo orquestador → agente implementador

1. Agente lee **solo** el mini-plan del hito activo + decisiones §4 (invariantes).
2. Agente implementa tasks en orden; **no salta tasks**.
3. Tras cada task: comandos de verificación del mini-plan (pytest exacto).
4. Orquestador revisa diff contra **Forbidden files** y **DoD parcial**.
5. Al cerrar hito: ejecutar **GATE** del mini-plan; marcar ✅ en esta tabla.
6. Siguiente hito desbloqueado.

---

## Protocolo anti-gap (desde Hito 6 — todos los hitos futuros)

Cada mini-plan incluye sección **Protocolo anti-gap**. Resumen global:

| Paso | Qué | Por qué |
|------|-----|---------|
| **Invariantes explícitas** | Lista I1–In en el mini-plan | El agente cumple tasks; el orquestador cumple el sistema |
| **Trace-the-flag** | `rg` de paths críticos antes de DONE | Detecta gates solo en `main.py` pero no en runtime/`.env` |
| **Segunda vía** | ¿`config_update`, WS, `.env` bypass el gate de arranque? | Evita bugs tipo commentary batch reactivable |
| **Tests reales** | Prohibido `assert True` / placeholder | “Hay test” ≠ “hay prueba” |
| **Entregable literal** | Pegar output GATE, no resumen | Orquestador no re-ejecuta a ciegas |

**Plantilla entregable agente → orquestador:**

```markdown
## Task NN — DONE
- Invariantes: I?
- Archivos: ...
- rg trace: (output)
- Segunda vía bypass: ninguna / (describir)
- GATE output: (últimas líneas)
- Placeholder tests: ninguno
```

**Checklist orquestador (5 min post-entrega):**

1. ¿Cada invariante tiene test o evidencia manual?
2. ¿Algún flag nuevo solo gated en un sitio?
3. ¿Tests nuevos fallarían si se quita el fix?
4. ¿Diff toca archivos FORBIDDEN?
5. ¿GATE output pegado literalmente?

---

## Forbidden global (todos los hitos)

- ❌ No crear segundo repo / carpeta paralela
- ❌ No `supervisor.ps1` ni segundo exe
- ❌ No mover LLM a proceso separado
- ❌ No refactorizar `crewchief_events/modules/*` (solo wiring)
- ❌ No tocar `shared-telemetry/` ni `shared-strategy/`
- ❌ No commits unless task step says so (or user asks)

---

## Comandos baseline (antes de cualquier hito)

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_spotter.py tests/test_config_update_ack_ws.py -q --tb=no
```

Expected: all passed (regression smoke before change).

---

## Registro de gates

| Hito | Fecha | Agente | GATE | Notas |
|------|-------|--------|------|-------|
| 1 | 2026-06-07 | implementador | ✅ | race_tick_loop global; CC fuera de WS; 6/6 race GATE ✅; `test_config_update_ack_ws` excluido (deuda config `SPOTTER_CAR_LENGTH_M`) |
| 2 | 2026-06-07 | implementador | ✅ | 16+20 tests; VoiceBridge wired; revisión orquestador OK |
| 3 | 2026-06-07 | implementador | ✅ | Tests OK; Pygame wiring roto en runtime — hotfix Task 17 en Hito 4 |
| 4 | 2026-06-07 | orquestador | ✅ | Task 25 useWebSocket aplicada post-review; backend+frontend GATE OK |
| 5 | 2026-06-07 | orquestador | ✅ | BETA_SLIM gates reforzados; doctor exit 1 sin _internal; tests slim reales |
| 6 | 2026-06-07 | orquestador | ✅ | Suite 1016+277 green; NATIVE_TELEMETRY fix; gate reforzado |
| 7 | 2026-06-11 | implementador | ✅ | setup 0.2.13; verify_bundle_startup PygameAudioPlayer ticks≥131; verify-release ALL PASS; LMU native smoke; duck_lmu WARN |
| 8 | 2026-06-11 | implementador | ✅ | Matriz D1–D12; lifespan integration; bundle_freshness fix; V1 pista PASS piloto |
