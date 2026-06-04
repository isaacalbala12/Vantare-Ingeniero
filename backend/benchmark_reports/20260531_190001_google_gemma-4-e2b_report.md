# Benchmark LLM: google/gemma-4-e2b

- **Endpoint**: http://192.168.1.41:1234
- **Modelo**: google/gemma-4-e2b
- **Fecha**: 2026-05-31 19:00
- **Duracion total**: 841s
- **Total prompts**: 140

## Resultados por Nivel

| Nivel | Nombre | Pts | Prompts | Aciertos | Aprobado | TTFT(ms) | Tok/s |
|-------|--------|:---:|:-------:|:--------:|:--------:|:--------:|:-----:|
| L1 | Extraccion de campos | 71.7% | 31 | 27/31 | NO PASA | 3515ms | 6.0 |
| L2 | Interpretacion de campos | 42.0% | 20 | 10/20 | NO PASA | 4322ms | 9.7 |
| L3 | Respuesta a triggers | 14.5% | 19 | 1/19 | NO PASA | 6872ms | 8.6 |
| L4 | Razonamiento multicampo | 36.6% | 20 | 12/20 | NO PASA | 6809ms | 8.7 |
| L5 | Razonamiento con RAG | 33.2% | 15 | 8/15 | NO PASA | 6176ms | 8.0 |
| L6 | Estrategia multi-trigger | 31.2% | 10 | 3/10 | NO PASA | 7251ms | 9.1 |
| L7 | Casos limite y anomalias | 25.9% | 15 | 5/15 | NO PASA | 5462ms | 8.5 |
| L8 | Razonamiento temporal | 12.8% | 10 | 2/10 | PASA | 6115ms | 9.4 |

## Resumen Global

- **Nivel maximo aprobado**: L8
- **Prompts totales**: 140
- **Aciertos totales**: 68/140 (48.6%)
- **Puntuacion ponderada (por nivel)**: 27.3%

## Matriz de Aprobacion

```
L1 [##############------] 71.7% (min 90.0%) X
L2 [########------------] 42.0% (min 85.0%) X
L3 [##------------------] 14.5% (min 80.0%) X
L4 [#######-------------] 36.6% (min 75.0%) X
L5 [######--------------] 33.2% (min 70.0%) X
L6 [######--------------] 31.2% (min 65.0%) X
L7 [#####---------------] 25.9% (min 60.0%) X
L8 [##------------------] 12.8% (min 0.0%) >
```

## Debilidades Detectadas

- **L1.13** (A): ?... (score: 0.0%)
- **L2.8** (H): ?... (score: 0.0%)
- **L2.11** (A): ?... (score: 0.0%)
- **L2.14** (A): ?... (score: 16.7%)
- **L3.2** (A): ?... (score: 0.0%)
- **L3.3** (C): ?... (score: 0.0%)
- **L3.4** (A): ?... (score: 0.0%)
- **L3.9** (F): ?... (score: 0.0%)
- **L3.10** (B): ?... (score: 8.3%)
- **L3.11** (A): ?... (score: 10.0%)
_... y 22 debilidades mas._

---
_Generado por Vantare Benchmark LLM v1.0_