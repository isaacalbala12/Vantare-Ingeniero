# Fase 4: Ticker Compacto + Prompt Builder

**Goal:** Implementar el formato ticker compacto para reemplazar el JSON verboso en los prompts del LLM, refactorizar el context_builder y actualizar prompt_templates.

**Dependencies:** Fase 3 (RAG) ya completada. EventStore funcional.
**Architecture doc:** `docs/ai/orchestrator.md` (sección Fase 4)
**LMU reference docs:** `LMU/`

---

## Phases

### Phase 0: LiveContextManager — Auditoría y corrección de campos
**Status:** pending
**Files:**
- `backend/src/intelligence/live_context.py` (MODIFY)

**Tasks:**
- [ ] T0.1: Añadir `speed` (m/s), `track_grip_level`, `cloud_coverage`, `raining` a snapshots _fast/_standard/_deep
- [ ] T0.2: CORREGIR línea 145: cambiar `brake_wear_fl * 0.1` (labeled "aero") por `damage_aero` real
- [ ] T0.3: Añadir método `update_realtime(telemetry_dict, strategy_dict)` para datos frescos entre vueltas
- [ ] T0.4: Tests: verificar que snapshots contienen los nuevos campos

**Razón:** Los 3 subagentes confirmaron que live_context.py ignora `speed`, `track_grip_level`, y tiene un proxy incorrecto de brake_wear→aero.

### Phase 1: `ticker.py` — Generador de ticker
**Status:** pending
**Files:**
- `backend/src/intelligence/ticker.py` (CREATE)

**Tasks:**
- [ ] T1.1: Crear `ticker.py` con función `generate_ticker(data: dict) -> str`
- [ ] T1.2: Implementar línea DRV (posición, vuelta, combustible, neumáticos)
- [ ] T1.3: Implementar línea BRK (desgaste frenos vía lmu_api, omitir si cache vacío)
- [ ] T1.4: Implementar línea GAP (gaps con rivales delante/detrás)
- [ ] T1.5: Implementar línea SES (tipo sesión, tiempo restante)
- [ ] T1.6: Implementar línea WTH (clima, agarre, SC)
- [ ] T1.7: Implementar línea RIV con anillos de proximidad (CLS1/CLS2/FAR/LAP)
- [ ] T1.8: Implementar función `abbreviate_name(name: str) -> str` (3 chars)
- [ ] T1.9: Tests unitarios para cada línea del ticker

### Phase 2: `context_builder.py` — Refactor para ticker
**Status:** pending
**Files:**
- `backend/src/intelligence/context_builder.py` (MODIFY)

**Tasks:**
- [ ] T2.1: Agregar `_build_ticker_data(snapshot, telemetry_frame, strategy_advice, lmu_api) -> dict`
- [ ] T2.2: Integrar `generate_ticker()` en el flujo de build_prompt (usando ticker_data, NO modificar firma)
- [ ] T2.3: Integrar token counting con tiktoken (threshold de seguridad 3000 tokens)
- [ ] T2.4: Implementar degradación de tier (RAG → RIV FAR → ticker básico)
- [ ] T2.5: Tests: verificar que el prompt generado contiene ticker en vez de JSON

**Decisión de diseño (subagente 2):** NO modificar la firma de `build_prompt()`. En vez de pasar `telemetry_frame` y `strategy_advice` como parámetros, `_build_ticker_data()` se alimenta del snapshot MEJORADO (Phase 0) + consulta directa a `lmu_api.get_additional_data("brakes")` + datos de competitors ya en snapshot. Esto evita acoplamiento innecesario.

### Phase 3: `prompt_templates.py` — System prompt con diccionario ticker
**Status:** pending
**Files:**
- `backend/src/intelligence/prompt_templates.py` (MODIFY)

**Tasks:**
- [ ] T3.1: Crear `SYSTEM_PROMPT_TICKER` con tabla diccionario del formato
- [ ] T3.2: Modificar `render()` para usar ticker text plano en vez de json.dumps
- [ ] T3.3: Mantener tiers FAST/STANDARD/DEEP con ticker en todos
- [ ] T3.4: Verificar que el system prompt + ticker + RAG + trigger ≤ ~800 tokens

### Phase 4: `engine.py` — Integración final
**Status:** pending
**Files:**
- `backend/src/intelligence/engine.py` (MODIFY)

**Tasks:**
- [ ] T4.1: Llamar `live_context.update_realtime(telemetry_dict, strategy_dict)` en cada ciclo evaluate_cycle()
- [ ] T4.2: Pasar `self.lmu_api` a `context_builder.build_prompt()` (o a `_build_ticker_data`)
- [ ] T4.3: Tests de integración: ciclo engine completo con ticker

**Nota:** NO crear duplicado de "Déjame revisarlo...". Ya existe `LLMPendingMessage` en engine.py líneas 173-179.

### Phase 5: Tests de regresión
**Status:** pending
**Files:**
- `backend/tests/test_ticker.py` (CREATE)
- `backend/tests/test_context_builder.py` (MAYBE MODIFY)
- `backend/tests/test_engine.py` (MAYBE MODIFY)

**Tasks:**
- [ ] T5.1: Tests unitarios para generate_ticker con datos mock
- [ ] T5.2: Tests de integración: context_builder con ticker + RAG
- [ ] T5.3: Verificar que tests existentes siguen pasando (regresión)
- [ ] T5.4: Verificar que el prompt total está dentro del límite de tokens

---

## Subagent Review Results

### Subagente 1: live_context.py audit
| Hallazgo | Veredicto | Severidad |
|----------|:--------:|:---------:|
| No captura `speed` | CONFIRMADO | BAJO |
| No guarda `track_grip_level` | CONFIRMADO | MEDIO |
| Proxy brake_wear→aero (L145) | CONFIRMADO | **CRÍTICO** |
| Sin clima en tiempo real | CONFIRMADO | BAJO |

### Subagente 2: build_prompt() gap
| Hallazgo | Veredicto |
|----------|:--------:|
| build_prompt() no recibe datos frescos | CONFIRMADO |
| Solución: cambiar firma de build_prompt() | **REFUTADO** — mejor actualizar snapshots en live_context |

### Subagente 3: tyre_wear scale
| Hallazgo | Veredicto |
|----------|:--------:|
| Inconsistencia 0.0-1.0 vs 0-100 | **REFUTADO** — la cadena TelemetryFrame → live_context es 0-100 constante |

---

## Key Decisions

| Decisión | Opción | Razón |
|----------|--------|-------|
| Fuente brake wear | lmu_api.get_additional_data("brakes") | Shared memory no expone brake wear |
| RIV rivals | Anillos de proximidad (CLS1/CLS2/FAR/LAP) | Muestra todos los rivales con coste acotado |
| Token threshold | 3000 tokens con degradación | Protección contra bugs, no bloqueo funcional |
| Audio pending | No crear duplicado (ya existe LLMPendingMessage) | Ya implementado en engine.py |
| Identificador rival | Nombre abreviado 3 chars + pit group opcional | No existe dorsal en shared memory |
| Datos frescos en prompt | update_realtime() en live_context, NO modificar build_prompt() | Menor acoplamiento, snapshots autocontenidos |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| live_context L145: brake_wear como "aero" | — | Cambiar a damage_aero real + añadir brake_wear como campo separado |
