# Benchmark Progresivo de LLMs — Vantare Ingeniero IA

## Filosofia

No todos los LLMs sirven para ingeniería de carrera en español.
Este benchmark evalua modelos en **8 niveles de dificultad creciente**,
cada uno eliminando modelos que no lo superan.

El resultado no es solo "cual es mejor", sino **hasta donde llega cada modelo**.

## Arquitectura del Pipeline de Datos

```
LMU Shared Memory (50+ campos)
    |
    v
TelemetryReader -> RaceState (tyres, brakes, engine, session, rivals...)
    |
    v
StrategyService -> TelemetryFrame (50+ campos calculados)
    |
    +---> context_builder._build_ticker_data() -> ticker dict (20+ campos)
    |         |
    |         v
    |       generate_ticker() -> TICKER (6 lineas, ~400 tokens)
    |
    +---> format_event_text() -> RAG embedding (17 campos, ~120 chars)
    |         |
    |         v
    |       ChromaDB query -> top-5 eventos historicos (~100 tokens)
    |
    v
build_prompt() -> Prompt final (~800 tokens)
    |
    v
LLM (via LiteLLM/LM Studio/OpenAI API)
    |
    v
Respuesta streaming -> TTS -> voz al piloto
```

## Los 8 Niveles

### Nivel 1: Extraccion de Campos (30 prompts)
**Dificultad**: Muy facil
**Umbral**: 90%

El LLM recibe un ticker y debe extraer el valor exacto de un campo.

Ejemplo:
```
INPUT:  DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63.92/94/98/96
        BRK:38/35/22/20
        GAP>VST:+2.1.1:48.2|<ALO:-1.2.1:47.9.d-0.3
        SES:HY|RACE|38L|45:22
        WTH:MED|22|30%+15m|SC:N
QUESTION: Cual es el desgaste del neumatico delantero izquierdo?
EXPECTED: 72
```

**Filtro**: Elimina modelos que no entienden el formato ticker basico.

### Nivel 2: Interpretacion de Campos (20 prompts)
**Dificultad**: Facil
**Umbral**: 85%

Ya no extraer, sino interpretar el significado.

Ejemplo:
```
QUESTION: Vas ganando o perdiendo tiempo respecto al coche de detras?
TICKER:   GAP>VST:+2.1|<ALO:-1.2.d-0.3
EXPECTED: d-0.3 significa que eres 0.3s mas rapido -> estas ganando tiempo
```

### Nivel 3: Respuesta a Triggers (24 prompts)
**Dificultad**: Medio
**Umbral**: 80%

12 triggers del proyecto x 2 escenarios (activo/no activo). El LLM debe
responder como un ingeniero de carrera por radio.

Triggers evaluados: FuelCritical, SafetyCar, BrakeWearCritical,
TyreDegAccel, HybridDeployMap, WeatherChange, PitWindowOpened,
PitWindowClosing, CompetitorPitted, GapClosed, PhaseChanged,
TiresThermalOverheating.

### Nivel 4: Razonamiento Multicampo (20 prompts)
**Dificultad**: Medio-alto
**Umbral**: 75%

Debe cruzar 2+ lineas del ticker.

Ejemplo: WTH (80% lluvia en 3 min) + DRV (slicks 55% de vida)
-> Recomendar entrar a por intermedios.

### Nivel 5: Razonamiento con RAG (15 prompts)
**Dificultad**: Alto
**Umbral**: 70%

El prompt incluye `## RECORDATORIO HISTORICO` con eventos pasados.
Debe cruzar RAG + ticker actual.

Ejemplo: RAG muestra SC en V8, ticker muestra V12.
-> Calcular desgaste acumulado desde el SC.

### Nivel 6: Estrategia Multi-Trigger (10 prompts)
**Dificultad**: Experto
**Umbral**: 65%

Multiples triggers activos simultaneamente. Debe priorizar correctamente.

Ejemplo: FuelCritical (0L rest) + PitWindowClosing + CompetitorPitted
-> El LLM debe priorizar: entrar AHORA es la jugada correcta.

### Nivel 7: Casos Limite y Anomalias (15 prompts)
**Dificultad**: Experto+
**Umbral**: 60%

Datos en el borde, contradictorios, o campos ausentes.

Casos:
- Lap <= 3: ticker sin TYR -> No recomendar cambio de neumaticos
- Sin BRK: ticker sin frenos -> No mencionar frenos
- Temperaturas exactamente en el limite (105C)
- Velocidad 0 + in_pits = True (parado en boxes)

### Nivel 8: Razonamiento Temporal (10 prompts)
**Dificultad**: Maestro
**Umbral**: Sin umbral (ranking abierto)

Serie de 3-5 ticks consecutivos. Debe detectar tendencias.

Ejemplo: 3 ticks mostrando degradacion 72% -> 55% -> 42% en 4 vueltas
-> La degradacion se esta acelerando (12% -> 13% por vuelta).

## Evaluacion

### Evaluacion automatica (keyword + rubrica)

Cada prompt tiene:
- `expected_keywords`: palabras que DEBEN aparecer en la respuesta
- `rubric`: reglas especificas (recommends_pit, identifies_overheating, etc.)

La puntuacion combina:
1. **Keyword matching**: proporción de keywords presentes
2. **Rubric scoring**: cumple condiciones semanticas (recomendó entrar? mencionó combustible?)

### Evaluacion humana complementaria

El reporte incluye las respuestas literales de los prompts con baja
puntuacion para revision manual. Esto es util para:
- Detectar falsos positivos del keyword matching
- Evaluar matices que la rubric automatica no captura
- Identificar patrones de error consistentes

## Reglas de Paso

| Nivel | Minimo | Consecuencia |
|-------|--------|-------------|
| 1 | 90% | Filtro inicial: si no reconoce campos, no sigue |
| 2 | 85% | Filtro semantico basico |
| 3 | 80% | Filtro de triggers |
| 4 | 75% | Razonamiento empieza a diferenciar modelos |
| 5 | 70% | Pocos modelos pasan (solo los que entienden RAG) |
| 6 | 65% | Solo los mejores |
| 7 | 60% | Robustez en edge cases |
| 8 | — | Puntuacion abierta (ranking, no aprobar/suspender) |

## Interpretacion de Resultados

### Que significa cada nivel maximo aprobado

| Nivel maximo | Significado | Modelos tipicos |
|-------------|-------------|-----------------|
| L1-L2 | No sirve para el proyecto | Modelos <1B, multilingual debil |
| L3 | Sirve para triggers basicos | Gemma 2 2B, Phi-3.5-mini |
| L4 | Sirve para analisis general | Llama 3.2 3B |
| L5 | Sirve con RAG | Qwen 3.5 4B |
| L6 | Sirve para estrategia completa | Qwen 2.5 7B Q4 |
| L7-L8 | Excelente para todo | Modelos >7B o bien entrenados en español |

### Que mirar en el reporte

1. **Nivel maximo aprobado**: hasta donde llega el modelo
2. **Puntuacion ponderada**: calidad global (niveles altos pesan mas)
3. **Debilidades detectadas**: en que nivel concreto falla
4. **TTFT + Tokens/s**: latencia para uso en tiempo real (0.5Hz)
5. **Matriz de aprobacion**: visual rapida de strengths/weaknesses

## Uso

### Requisitos

```bash
pip install httpx
```

### Probar un modelo especifico

```bash
cd backend
python tests/benchmark_llm.py \
    --model qwen3.5-4b \
    --base-url http://192.168.1.41:1234/api/v1
```

### Probar solo un nivel

```bash
python tests/benchmark_llm.py \
    --model llama3.2-3b \
    --base-url http://192.168.1.41:1234/api/v1 \
    --level 3
```

### Comparar todos los modelos predefinidos

```bash
python tests/benchmark_llm.py \
    --base-url http://192.168.1.41:1234/api/v1 \
    --all
```

Esto evalua: Qwen 3.5 4B, Llama 3.2 3B, Phi-3.5-mini, Gemma 2 2B,
DeepSeek-R1-Distill-Qwen-7B, Qwen 2.5 7B.

### Dry-run (solo generar prompts)

```bash
python tests/benchmark_llm.py --dry-run
```

Muestra cuantos prompts se generan por nivel y un ejemplo del formato.

## Output

```
backend/tests/benchmark_reports/
├── 20260530_143000_qwen3.5-4b_report.md   # Reporte legible
├── 20260530_143000_qwen3.5-4b_data.json   # Datos crudos
├── 20260530_144500_llama3.2-3b_report.md
├── 20260530_144500_llama3.2-3b_data.json
└── ...
```

### Formato del reporte markdown

```markdown
# Benchmark LLM: qwen3.5-4b

- **Endpoint**: http://192.168.1.41:1234/api/v1
- **Total prompts**: 144
- **Duracion**: 342s

## Resultados por Nivel

| Nivel | Nombre | Pts | Prompts | Aciertos | TTFT(ms) | Tok/s |
|-------|--------|:---:|:-------:|:--------:|:--------:|:-----:|
| L1 | Extraccion | 95.0% | 30 | 28/30 | 340ms | 45.2 |
| L2 | Interpretacion | 88.0% | 20 | 17/20 | 355ms | 43.8 |
| ...

## Matriz de Aprobacion

L1 [##################--] 95.0% (min 90.0%) >
L2 [################---] 88.0% (min 85.0%) >
L3 [###############----] 80.0% (min 80.0%) >
L4 [#############------] 75.0% (min 75.0%) >
L5 [##########---------] 63.0% (min 70.0%) X
...

## Debilidades Detectadas
- L5.3 (A): Hemos perdido tiempo desde el SC... (score: 12.0%)
- L7.8 (F): Las temperaturas estan cerca del limite... (score: 8.0%)
```

## Modelos Recomendados para Probar

| Modelo | Parametros | VRAM | Cuantizacion | Notas |
|--------|-----------|------|-------------|-------|
| Qwen 3.5 4B | 4B | ~3.5GB | Q4 | Modelo actual, referencia |
| Qwen 3.5 4B | 4B | ~5GB | Q8 | Mayor calidad, mas VRAM |
| Qwen 2.5 7B | 7B | ~5.5GB | Q4 | Mas capacidad, misma VRAM |
| Llama 3.2 3B | 3B | ~4GB | Q8 | Rapido, buen español? |
| Phi-3.5-mini | 3.8B | ~5GB | Q8 | Bueno en ingles, probar español |
| Gemma 2 2B | 2B | ~3GB | Q8 | Ultra rapido, calidad? |
| DeepSeek-R1-Distill-Qwen-7B | 7B | ~5.5GB | Q4 | Razonamiento, pero lento |

## Personalizacion

### Anadir un modelo a la comparativa

Editar `DEFAULT_MODELS` en `benchmark_llm.py`:

```python
DEFAULT_MODELS = [
    {"model": "mi-modelo", "name": "Mi Modelo (Q4)"},
    ...
]
```

### Cambiar el umbral de aprobacion

Editar `PASS_THRESHOLDS`:

```python
PASS_THRESHOLDS = {
    1: 0.90,  # Mas estricto
    3: 0.75,  # Mas permisivo
    ...
}
```

### Anadir nuevos prompts

Editar las funciones `generate_level_X()` en `benchmark_llm.py`.
Cada prompt es un dict con:
```python
_p(
    ticker_id="A",                    # Referencia al ticker
    question="Tu pregunta aqui?",      # Pregunta al LLM
    expected=["keyword1", "keyword2"], # Keywords esperadas
    trigger="fuel_critical",          # Solo para nivel 3
    rag_context=_rag("..."),          # Solo para nivel 5+
    rubric={"recommends_pit": True},  # Reglas adicionales
)
```

## Notas Tecnicas

- La API debe ser OpenAI-compatible (LM Studio, LiteLLM, vLLM, Ollama, etc.)
- `temperature=0.1` para consistencia entre ejecuciones
- `max_tokens=300` (suficiente para respuestas de 2-3 frases)
- Tiempo de espera por prompt: 120s maximo
- El benchmark completo (~144 prompts) tira ~5-10 minutos por modelo
