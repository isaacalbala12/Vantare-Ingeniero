# Benchmark LLM: google/gemma-4-e4b

- **Endpoint**: http://192.168.1.41:1234
- **Modelo**: google/gemma-4-e4b
- **Fecha**: 2026-05-31 19:30
- **Duracion total**: 1523s
- **Total prompts**: 140

## Resultados por Nivel

| Nivel | Nombre | Pts | Prompts | Aciertos | Aprobado | TTFT(ms) | Tok/s |
|-------|--------|:---:|:-------:|:--------:|:--------:|:--------:|:-----:|
| L1 | Extraccion de campos | 70.6% | 31 | 26/31 | NO PASA | 6621ms | 6.1 |
| L2 | Interpretacion de campos | 51.6% | 20 | 12/20 | NO PASA | 8879ms | 7.5 |
| L3 | Respuesta a triggers | 17.2% | 19 | 1/19 | NO PASA | 11595ms | 6.8 |
| L4 | Razonamiento multicampo | 41.8% | 20 | 14/20 | NO PASA | 11827ms | 6.2 |
| L5 | Razonamiento con RAG | 32.5% | 15 | 8/15 | NO PASA | 11023ms | 6.6 |
| L6 | Estrategia multi-trigger | 33.0% | 10 | 2/10 | NO PASA | 12032ms | 6.2 |
| L7 | Casos limite y anomalias | 32.7% | 15 | 7/15 | NO PASA | 9043ms | 7.1 |
| L8 | Razonamiento temporal | 25.5% | 10 | 5/10 | PASA | 11077ms | 8.5 |

## Resumen Global

- **Nivel maximo aprobado**: L8
- **Prompts totales**: 140
- **Aciertos totales**: 75/140 (53.6%)
- **Puntuacion ponderada (por nivel)**: 32.9%

## Matriz de Aprobacion

```
L1 [##############------] 70.6% (min 90.0%) X
L2 [##########----------] 51.6% (min 85.0%) X
L3 [###-----------------] 17.2% (min 80.0%) X
L4 [########------------] 41.8% (min 75.0%) X
L5 [######--------------] 32.5% (min 70.0%) X
L6 [######--------------] 33.0% (min 65.0%) X
L7 [######--------------] 32.7% (min 60.0%) X
L8 [#####---------------] 25.5% (min 0.0%) >
```

## Debilidades Detectadas

- **L1.10** (A): ?... (score: 0.0%)
- **L1.13** (A): ?... (score: 0.0%)
- **L1.20** (B): ?... (score: 0.0%)
- **L2.20** (B): ?... (score: 0.0%)
- **L3.2** (A): ?... (score: 12.5%)
- **L3.3** (C): ?... (score: 0.0%)
- **L3.5** (E): ?... (score: 12.5%)
- **L3.7** (F): ?... (score: 8.3%)
- **L3.8** (C): ?... (score: 0.0%)
- **L3.9** (F): ?... (score: 8.3%)
_... y 18 debilidades mas._

---
_Generado por Vantare Benchmark LLM v1.0_