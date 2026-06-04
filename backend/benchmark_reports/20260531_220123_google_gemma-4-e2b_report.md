# Benchmark LLM: google/gemma-4-e2b

- **Endpoint**: http://192.168.1.41:1234
- **Modelo**: google/gemma-4-e2b
- **Fecha**: 2026-05-31 22:01
- **Duracion total**: 1002s
- **Total prompts**: 140

## Resultados por Nivel

| Nivel | Nombre | Pts | Prompts | Aciertos | Aprobado | TTFT(ms) | Tok/s |
|-------|--------|:---:|:-------:|:--------:|:--------:|:--------:|:-----:|
| L1 | Extraccion de campos | 69.9% | 31 | 27/31 | NO PASA | 3884ms | 5.5 |
| L2 | Interpretacion de campos | 43.0% | 20 | 9/20 | NO PASA | 4739ms | 8.5 |
| L3 | Respuesta a triggers | 16.3% | 19 | 3/19 | NO PASA | 7429ms | 9.5 |
| L4 | Razonamiento multicampo | 39.5% | 20 | 14/20 | NO PASA | 7477ms | 9.2 |
| L5 | Razonamiento con RAG | 35.8% | 15 | 9/15 | NO PASA | 7317ms | 7.8 |
| L6 | Estrategia multi-trigger | 32.0% | 10 | 3/10 | NO PASA | 7890ms | 7.1 |
| L7 | Casos limite y anomalias | 30.4% | 15 | 7/15 | NO PASA | 7160ms | 7.0 |
| L8 | Razonamiento temporal | 14.8% | 10 | 2/10 | PASA | 7301ms | 8.4 |

## Resumen Global

- **Nivel maximo aprobado**: L8
- **Prompts totales**: 140
- **Aciertos totales**: 74/140 (52.9%)
- **Puntuacion ponderada (por nivel)**: 29.6%

## Matriz de Aprobacion

```
L1 [#############-------] 69.9% (min 90.0%) X
L2 [########------------] 43.0% (min 85.0%) X
L3 [###-----------------] 16.3% (min 80.0%) X
L4 [#######-------------] 39.5% (min 75.0%) X
L5 [#######-------------] 35.8% (min 70.0%) X
L6 [######--------------] 32.0% (min 65.0%) X
L7 [######--------------] 30.4% (min 60.0%) X
L8 [##------------------] 14.8% (min 0.0%) >
```

## Debilidades Detectadas

- **L1.13** (A): ?... (score: 0.0%)
- **L1.24** (D): ?... (score: 0.0%)
- **L1.29** (E): ?... (score: 0.0%)
- **L2.7** (E): ?... (score: 0.0%)
- **L2.14** (A): ?... (score: 16.7%)
- **L2.20** (B): ?... (score: 0.0%)
- **L3.2** (A): ?... (score: 0.0%)
- **L3.3** (C): ?... (score: 0.0%)
- **L3.4** (A): ?... (score: 0.0%)
- **L3.5** (E): ?... (score: 12.5%)
_... y 27 debilidades mas._

---
_Generado por Vantare Benchmark LLM v1.0_