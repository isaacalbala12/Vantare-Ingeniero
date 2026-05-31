# Benchmark LLM: olmo-3-7b-think (RESULTADO ANTERIOR - 2048 tokens)

> Modelo removido de la tanda actual porque usaba ~8000 tokens de razonamiento
> por prompt sin llegar a producir respuesta final. Inviable en produccion.

- **Duracion total**: 4008s (67 min)
- **Total prompts**: 140
- **Problema**: El 90% de los prompts solo produjeron `reasoning_content`
  (pensamiento en ingles, ~7000 chars cada uno) sin llegar a generar `content`
  (respuesta final en espanol). Con 2048 tokens de limite, se agotaban antes
  de responder. Con tokens ilimitados, cada prompt tardaria ~30s+ en producir
  la respuesta final, lo que da ~4200s (70 min) para 140 prompts.

## Resultados

| Nivel | Puntuacion | Aciertos |
|-------|-----------|----------|
| L1 Extraccion | 64.0% | 21/31 |
| L2 Interpretacion | 52.7% | 12/20 |
| L3 Triggers | 9.7% | 1/19 |
| L4 Multicampo | 18.2% | 6/20 |
| L5 RAG | 25.9% | 6/15 |
| L6 Multi-trigger | 3.0% | 0/10 |
| L7 Edge cases | 23.3% | 5/15 |
| L8 Temporal | 3.3% | 1/10 |

## Veredicto

**No recomendado para produccion.** El costo de razonamiento (~8k tokens por
respuesta) hace que cada interaccion tarde ~30-60s, inaceptable para un
sistema de radio en tiempo real (0.5Hz = 2s maximo).
