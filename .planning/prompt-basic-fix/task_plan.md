# Plan: Ajustar SYSTEM_PROMPT_BASIC

## Decisión aprobada

`SYSTEM_PROMPT_BASIC` corregido:
- Elimina arrogancia ("Mantén el foco en la pista")
- No filtra preguntas no relacionadas
- Abierto a cualquier pregunta
- Conciso y directo

```python
SYSTEM_PROMPT_BASIC = (
    "Eres un ingeniero de carrera para Le Mans Ultimate. Sé conciso, directo y útil. "
    "Responde en 1-3 frases máximo. Estilo radio/comunicación de ingeniería."
)
```

---

## Tareas

### Fase 1: Actualizar SYSTEM_PROMPT_BASIC
- [x] Editar `backend/src/intelligence/prompt_templates.py`
- [x] Reemplazar prompt actual con el nuevo
- [x] Commit cambios

### Fase 2: Verificar
- [ ] Probar respuesta a "2+2?"
- [ ] Confirmar que responde de forma natural

---

## Estado
- **Estado**: En progreso
- **Fechainicio**: 2026-05-26
- **Completado por**: Decisión de diseño aprobada
