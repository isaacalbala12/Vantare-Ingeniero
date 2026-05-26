# Plan: Unificar prompts del LLM en prompt_templates.py

## Meta
Eliminar el system prompt duplicado que causa respuestas incoherentes del LLM.
El flujo debe mantener comportamiento dual: CON telemetría vs SIN telemetría.

## Estado actual

### El problema
- `llm_client.py` importa `SYSTEM_PROMPT_WEC` y lo añade como segundo role=system
- El LLM recibe DOBLE system prompt:
  1. `{"role": "system", "content": "Responde de forma concisa..."}` (SYSTEM_PROMPT_WEC)
  2. `{"role": "user", "content": "...SYSTEM_PROMPT_BASIC + contexto..."}` (render())

### Cómo funciona HOY
```
endpoint /ask
  → engine.ask_async()
    → context_builder.build_prompt_for_question() → render()
      → SI telemetría: SYSTEM_PROMPT_WEC + telemetry_section
      → NO telemetría: SYSTEM_PROMPT_BASIC + pregunta
    → llm_client.ask_streaming_text()
      → LLM recibe: SYSTEM_PROMPT_WEC + prompt_completo  ← DOBLE!
```

### Cómo funcionará DESPUÉS
```
endpoint /ask
  → engine.ask_async()
    → context_builder.build_prompt_for_question() → render()
      → SI telemetría: SYSTEM_PROMPT_BASIC + telemetry_section
      → NO telemetría: SYSTEM_PROMPT_BASIC + pregunta
    → llm_client.ask_streaming_text()
      → LLM recibe: SOLO prompt_completo (sin wrapper adicional)
```

---

## Fases

### Fase 1: Modificar prompt_templates.py
- [ ] Eliminar `SYSTEM_PROMPT_WEC` (ya no se usa fuera de la unificación)
- [ ] Mantener `SYSTEM_PROMPT_BASIC` como único prompt base
- [ ] Actualizar función `render()` para detectar telemetría y usar BASCI
- [ ] commit

### Fase 2: Modificar llm_client.py
- [ ] Eliminar import de `SYSTEM_PROMPT_WEC`
- [ ] `ask_streaming()`: usar SOLO el prompt recibido (sin wrapper)
- [ ] `ask_streaming_text()`: usar SOLO el prompt recibido (sin wrapper)
- [ ] Mantener `UI_TOOLS` para acciones visuales (no afecta prompts)
- [ ] commit

### Fase 3: Actualizar engine.py
- [ ] Verificar que `build_prompt()` y `build_prompt_for_question()` ya construyen prompt completo
- [ ] Verificar que no pasa system prompt adicional a llm_client
- [ ] commit

### Fase 4: Tests
- [ ] Ejecutar `pytest backend/tests/test_llm_async.py`
- [ ] Ejecutar `pytest backend/tests/test_preemption.py`
- [ ] Verificar que tests siguen pasando
- [ ] commit

### Fase 5: Verificación E2E
- [ ] Probar sin telemetría: `curl -X POST http://localhost:8008/ask -d '{"question":"2+2"}'`
- [ ] Expected: respuesta simple "4"
- [ ] Probar con telemetría: envío de datos de carrera real
- [ ] Expected: ingeniero contextual con datos de carrera
- [ ] commit

### Fase 6: Cleanup legacy
- [ ] Revisar `llm_service.py` - ¿sigue usándose o es legacy?
- [ ] Marcar como deprecated si no se usa
- [ ] commit

---

## Decisiones clave documentadas
- MANTENER: `_has_telemetry()` para detectar si hay datos reales
- MANTENER: lógica de `tier` (FAST/STANDARD/DEEP) para nivel de detalle
- ELIMINAR: `SYSTEM_PROMPT_WEC` como constante separada
- UNIFICAR: siempre usar `SYSTEM_PROMPT_BASIC`不管 haya telemetría o no

## open questions
- [ ] ¿ `llm_service.py` (`llamar_copiloto_stream`) sigue en uso o es legacy de CrofAI?
- [ ] ¿Los tests asumen que `ask_streaming()` tiene system wrapper? (debe verificarse)

---

## Estado
- **Status**: En planificación
- **Fecha inicio**: 2026-05-26
- **Completado por**: Aprobación del usuario tras brainstorm
