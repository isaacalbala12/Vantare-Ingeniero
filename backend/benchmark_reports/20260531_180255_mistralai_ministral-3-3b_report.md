# Benchmark LLM: mistralai/ministral-3-3b

- **Endpoint**: http://192.168.1.41:1234
- **Modelo**: mistralai/ministral-3-3b
- **Fecha**: 2026-05-31 18:02
- **Duracion total**: 262s
- **Total prompts**: 140

## Resultados por Nivel

| Nivel | Nombre | Pts | Prompts | Aciertos | Aprobado | TTFT(ms) | Tok/s |
|-------|--------|:---:|:-------:|:--------:|:--------:|:--------:|:-----:|
| L1 | Extraccion de campos | 70.1% | 31 | 26/31 | NO PASA | 189ms | 64.3 |
| L2 | Interpretacion de campos | 58.5% | 20 | 13/20 | NO PASA | 246ms | 69.1 |
| L3 | Respuesta a triggers | 15.9% | 19 | 2/19 | NO PASA | 268ms | 75.9 |
| L4 | Razonamiento multicampo | 44.3% | 20 | 15/20 | NO PASA | 244ms | 75.3 |
| L5 | Razonamiento con RAG | 34.4% | 15 | 8/15 | NO PASA | 255ms | 72.1 |
| L6 | Estrategia multi-trigger | 24.4% | 10 | 1/10 | NO PASA | 247ms | 74.0 |
| L7 | Casos limite y anomalias | 33.4% | 15 | 7/15 | NO PASA | 226ms | 71.5 |
| L8 | Razonamiento temporal | 24.6% | 10 | 4/10 | PASA | 204ms | 77.2 |

## Resumen Global

- **Nivel maximo aprobado**: L8
- **Prompts totales**: 140
- **Aciertos totales**: 76/140 (54.3%)
- **Puntuacion ponderada (por nivel)**: 32.2%

## Matriz de Aprobacion

```
L1 [##############------] 70.1% (min 90.0%) X
L2 [###########---------] 58.5% (min 85.0%) X
L3 [###-----------------] 15.9% (min 80.0%) X
L4 [########------------] 44.3% (min 75.0%) X
L5 [######--------------] 34.4% (min 70.0%) X
L6 [####----------------] 24.4% (min 65.0%) X
L7 [######--------------] 33.4% (min 60.0%) X
L8 [####----------------] 24.6% (min 0.0%) >
```

## Debilidades Detectadas

- **L1.25** (D): ?... (score: 0.0%)
- **L1.26** (D): ?... (score: 0.0%)
- **L1.31** (F): ?... (score: 0.0%)
- **L2.20** (B): ?... (score: 0.0%)
- **L3.2** (A): ?... (score: 12.5%)
- **L3.3** (C): ?... (score: 0.0%)
- **L3.4** (A): ?... (score: 16.7%)
- **L3.7** (F): ?... (score: 8.3%)
- **L3.8** (C): ?... (score: 10.0%)
- **L3.9** (F): ?... (score: 8.3%)
_... y 21 debilidades mas._

---
_Generado por Vantare Benchmark LLM v1.0_