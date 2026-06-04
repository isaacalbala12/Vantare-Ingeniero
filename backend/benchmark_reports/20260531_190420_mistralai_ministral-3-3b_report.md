# Benchmark LLM: mistralai/ministral-3-3b

- **Endpoint**: http://192.168.1.41:1234
- **Modelo**: mistralai/ministral-3-3b
- **Fecha**: 2026-05-31 19:04
- **Duracion total**: 238s
- **Total prompts**: 140

## Resultados por Nivel

| Nivel | Nombre | Pts | Prompts | Aciertos | Aprobado | TTFT(ms) | Tok/s |
|-------|--------|:---:|:-------:|:--------:|:--------:|:--------:|:-----:|
| L1 | Extraccion de campos | 76.5% | 31 | 29/31 | NO PASA | 171ms | 72.1 |
| L2 | Interpretacion de campos | 51.7% | 20 | 13/20 | NO PASA | 220ms | 79.1 |
| L3 | Respuesta a triggers | 20.0% | 19 | 3/19 | NO PASA | 253ms | 85.7 |
| L4 | Razonamiento multicampo | 43.3% | 20 | 15/20 | NO PASA | 240ms | 83.5 |
| L5 | Razonamiento con RAG | 35.4% | 15 | 8/15 | NO PASA | 250ms | 80.7 |
| L6 | Estrategia multi-trigger | 31.3% | 10 | 2/10 | NO PASA | 260ms | 83.2 |
| L7 | Casos limite y anomalias | 38.5% | 15 | 9/15 | NO PASA | 205ms | 81.0 |
| L8 | Razonamiento temporal | 20.0% | 10 | 4/10 | PASA | 190ms | 86.2 |

## Resumen Global

- **Nivel maximo aprobado**: L8
- **Prompts totales**: 140
- **Aciertos totales**: 83/140 (59.3%)
- **Puntuacion ponderada (por nivel)**: 33.5%

## Matriz de Aprobacion

```
L1 [###############-----] 76.5% (min 90.0%) X
L2 [##########----------] 51.7% (min 85.0%) X
L3 [###-----------------] 20.0% (min 80.0%) X
L4 [########------------] 43.3% (min 75.0%) X
L5 [#######-------------] 35.4% (min 70.0%) X
L6 [######--------------] 31.3% (min 65.0%) X
L7 [#######-------------] 38.5% (min 60.0%) X
L8 [####----------------] 20.0% (min 0.0%) >
```

## Debilidades Detectadas

- **L1.31** (F): ?... (score: 0.0%)
- **L2.1** (A): ?... (score: 0.0%)
- **L2.6** (F): ?... (score: 0.0%)
- **L2.8** (H): ?... (score: 16.7%)
- **L2.20** (B): ?... (score: 0.0%)
- **L3.2** (A): ?... (score: 12.5%)
- **L3.3** (C): ?... (score: 0.0%)
- **L3.4** (A): ?... (score: 16.7%)
- **L3.9** (F): ?... (score: 8.3%)
- **L3.10** (B): ?... (score: 8.3%)
_... y 18 debilidades mas._

---
_Generado por Vantare Benchmark LLM v1.0_