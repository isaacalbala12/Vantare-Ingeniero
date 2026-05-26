# Findings: Unificación de prompts LLM

## Research: Cómo-funciona-el-flujo-LLM-hoy

### Endpoint /ask
```python
POST /ask → AskRequest(question, chat_history)
```

### Router (llm.py)
```python
async def ask_copilot(request: Request, body: AskRequest):
    engine = request.app.state.intelligence_engine
    formatted_history = [...]
    full_response = ""
    async for chunk in engine.ask_async(body.question, formatted_history):
        full_response += chunk
    return Response(content=full_response, media_type="text/plain")
```

### IntelligenceEngine.ask_async() (engine.py:324)
```python
async def ask_async(self, pilot_question: str, chat_history: list = None):
    snapshot = self.live_context.snapshot(tier="FAST")
    if strategy_service:
        race_summary = strategy_service.get_race_summary()
        # merge into snapshot
    
    prompt = self.context_builder.build_prompt_for_question(
        snapshot=snapshot,
        pilot_question=pilot_question,
        chat_history=chat_history,
        templates=self.prompt_templates
    )
    
    async for token in self.llm_client.ask_streaming_text(prompt, tier="FAST"):
        full_text += token
    yield full_text
```

### context_builder.build_prompt_for_question() (context_builder.py:22)
```python
def build_prompt_for_question(snapshot, pilot_question, chat_history, templates):
    context_dict = {"snapshot": snapshot, "pilot_question": pilot_question}
    if chat_history:
        context_dict["chat_history"] = chat_history
    
    tier = "FAST"
    if snapshot.get("lap_number", 0) > 0 and (snapshot.get("speed") or snapshot.get("fuel")):
        tier = "STANDARD"
    if snapshot.get("weather_forecast"):
        tier = "DEEP"
    
    return templates.render(context_dict, tier)
```

### prompt_templates.render() (fragmento)
```python
def render(context_dict: dict, tier: str) -> str:
    has_telemetry = _has_telemetry(context_dict)
    if has_telemetry:
        system_prompt = SYSTEM_PROMPT_WEC  # ← "Responde de forma concisa y directa."
        ...
        return f"{system_prompt}\n\n{telemetry_section}"
    else:
        system_prompt = SYSTEM_PROMPT_BASIC
        ...
        return f"{system_prompt}\n\nPREGUNTA DEL PILOTO:\n{pilot_question}"
```

### llm_client.ask_streaming_text() (llm_client.py:206)
```python
async def ask_streaming_text(self, prompt: str, tier: str = "FAST"):
    payload = {
        "model": self._model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},  # ← SISTEMA_EXTERNO: "Responde de forma concisa..."
            {"role": "user", "content": prompt},            # ← prompt ya contiene OTRO system prompt dentro
        ],
        ...
    }
```

### EL PROBLEMA: Doble system prompt
```
1. ask_streaming_text añade: role=system "Responde de forma concisa y directa."
2. El prompt ya Contiene: role=user "...Eres un ingeniero de carrera..."

EL LLM RECIBE DOS SYSTEMAS EN CONFLICTO
```

---

## Research: Componentes-main-que-usan-llm_client

### 1. engine._run_llm_stream() → ask_streaming()
- **Quién llama**: engine.evaluate_cycle() cuando un trigger requiere LLM
- **Qué hace**: emite WebSocket messages (advice_start, advice_token, advice_end)
- **UI tools**: Sí, soporta tool_calls para acciones visuales

### 2. engine.ask_async() → ask_streaming_text()
- **Quién llama**: router /ask endpoint
- **Qué hace**: devuelve texto directo por HTTP
- **UI tools**: No

### 3. llm_service.llamar_copiloto_stream()
- **Quién llama**: ¿alguien? No encontrado en imports
- **Tiene su propio system prompt**: "Eres el Ingeniero de Carrera Principal..."
- **STATE**: Possible legacy de CrofAI

---

## Research: Tests-que-hacen-mock-de-llm_client

### test_llm_async.py
```python
# Mock de _get_client y chat.completions.create
mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)
await client.ask_streaming("test prompt", "FAST", "advice-123", None)

# Verifica: start_msgs, token_msgs, end_msgs
# El test PASA el prompt como parámetro → no depende de system wrapper
```

### test_preemption.py
```python
async def mock_streaming(self, prompt, tier, advice_id, engine_ref=None):
    yield {"type": "token", "content": " térmico: "}
    yield {"type": "token", "content": "reduce ritmo."}

engine.llm_client.ask_streaming = mock_streaming
```

**Conclusión**: Los tests mockean `ask_streaming()` directamente, pasan el prompt como parámetro y NO verifican contenido del system prompt. Deberían seguir pasando.

---

## Research: UI_TOOLS-no-depende-del-prompt

`UI_TOOLS` es una constante con estructura de tools de OpenAI:
```python
UI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "trigger_ui_alert",
            ...
        }
    }
]
```

Se pasa como parámetro `stream_options` o `tools` en la llamada API, NO en el system prompt.

---

## Research: Flujo-SIN-telemetría-que-debe-funcionar

El piloto pregunta "2+2" SIN estar en carrera (sin telemetría):

1. `live_context.snapshot("FAST")` → vacío o datos mínimos (sin `lap`, `speed`, `fuel`)
2. `_has_telemetry()` → `False` (líneas 46-53)
3. `render()` → usa `SYSTEM_PROMPT_BASIC` + pregunta
4. El prompt resultante:
   ```
   Eres un ingeniero de carrera para Le Mans Ultimate. Sé conciso, directo y útil.
   Responde en 1-3 frases máximo. Estilo radio/comunicación de ingeniería.

   PREGUNTA DEL PILOTO:
   ¿Cuánto es 2+2?
   ```
5. LLM debería responder: "4."

**El PROBLEMA Actual**: `llm_client.ask_streaming_text()` AÑADE otro system prompt antes de este → el LLM se confunde.

---

## Research: Flujo-CON-telemetría-que-debe-funcionar

Durante carrera con datos reales:

1. `live_context.snapshot("STANDARD")` → datos completos (lap, speed, fuel, tyres, etc.)
2. `_has_telemetry()` → `True`
3. `render()` → usa `SYSTEM_PROMPT_BASIC` + telemetry_section + instrucciones
4. El prompt resultante:
   ```
   Eres un ingeniero de carrera... (BASIC)

   ### CONTEXTO DE TELEMETRÍA (STANDARD) ###
   {...datos de carrera...}

   INSTRUCCIÓN: Analiza los datos de carrera. Responde al piloto de forma ultra corta...
   Si la telemetría lo requiere, activa la herramienta 'trigger_ui_alert'.
   ```
5. LLM debería dar consejos específicos de carrera basándose en los datos.

---

## Decisiones descartadas

- **Opción B (pass system prompt como parámetro)**: Añade complejidad innecesaria. `context_builder` ya construye el prompt completo.
- **Eliminar `SYSTEM_PROMPT_WEC` por completo**: No viable. La lógica de `render()` necesita detectar telemetría y usar BASCI en ambos casos (con o sin telemetría).
- **Mantener dos prompts separados (BASIC/WEC)**: Problema resuelto - ya no hay doblo wrapper en `llm_client`.

---

## Ver también
- `docs/ai/tasks/2026-05-26-orquestador.md` - estado del proyecto
- `backend/src/intelligence/prompt_templates.py` - el archivo a modificar
- `backend/src/intelligence/llm_client.py` - el archivo a modificar
