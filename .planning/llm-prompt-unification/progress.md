# Progress

## 2026-05-26

### Inicio
- User solicitó brainstorm sobre SYSTEM_PROMPT_BASIC
- Decisión: unificar prompts para eliminar duplicación
- Creado plan extensivo en `.planning/llm-prompt-unification/`

### Investigación completada
- [x] Identificado el problema: doble system prompt en `llm_client`
- [x] Documentado el flujo completo desde `/ask` hasta LLM
- [x] Verificado que tests hacen mock directo de `ask_streaming()` - no dependen de system wrapper
- [x] Confirmado que UI_TOOLS es independiente del prompt

### Implementación completada
- [x] Fase 1: Modificar `prompt_templates.py` - listo
- [x] Fase 2: Modificar `llm_client.py` - listo
- [x] Fase 3: Verificar `engine.py` - listo
- [x] Fase 4: Tests - 5/5 pasaron

### Pendiente
- Fase 5: Verificación E2E (manual - backend en otra máquina)
- Fase 6: Cleanup legacy `llm_service.py`
