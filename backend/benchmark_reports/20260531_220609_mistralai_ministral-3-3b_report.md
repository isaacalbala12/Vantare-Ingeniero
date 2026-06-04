# Benchmark LLM: mistralai/ministral-3-3b

- **Endpoint**: http://192.168.1.41:1234
- **Modelo**: mistralai/ministral-3-3b
- **Fecha**: 2026-05-31 22:06
- **Duracion total**: 266s
- **Total prompts**: 140

## Resultados por Nivel

| Nivel | Nombre | Pts | Prompts | Aciertos | Aprobado | TTFT(ms) | Tok/s |
|-------|--------|:---:|:-------:|:--------:|:--------:|:--------:|:-----:|
| L1 | Extraccion de campos | 79.1% | 31 | 29/31 | NO PASA | 178ms | 69.7 |
| L2 | Interpretacion de campos | 58.0% | 20 | 15/20 | NO PASA | 240ms | 75.2 |
| L3 | Respuesta a triggers | 23.1% | 19 | 3/19 | NO PASA | 263ms | 83.9 |
| L4 | Razonamiento multicampo | 45.2% | 20 | 13/20 | NO PASA | 251ms | 78.8 |
| L5 | Razonamiento con RAG | 34.1% | 15 | 7/15 | NO PASA | 255ms | 76.6 |
| L6 | Estrategia multi-trigger | 34.8% | 10 | 3/10 | NO PASA | 274ms | 78.0 |
| L7 | Casos limite y anomalias | 40.2% | 15 | 8/15 | NO PASA | 240ms | 76.4 |
| L8 | Razonamiento temporal | 18.4% | 10 | 3/10 | PASA | 223ms | 79.6 |

## Resumen Global

- **Nivel maximo aprobado**: L8
- **Prompts totales**: 140
- **Aciertos totales**: 81/140 (57.9%)
- **Puntuacion ponderada (por nivel)**: 34.8%

## Matriz de Aprobacion

```
L1 [###############-----] 79.1% (min 90.0%) X
L2 [###########---------] 58.0% (min 85.0%) X
L3 [####----------------] 23.1% (min 80.0%) X
L4 [#########-----------] 45.2% (min 75.0%) X
L5 [######--------------] 34.1% (min 70.0%) X
L6 [######--------------] 34.8% (min 65.0%) X
L7 [########------------] 40.2% (min 60.0%) X
L8 [###-----------------] 18.4% (min 0.0%) >
```

## Debilidades Detectadas

- **L1.31** (F): ?... (score: 0.0%)
- **L2.1** (A): ?... (score: 0.0%)
- **L2.6** (F): ?... (score: 14.3%)
- **L3.3** (C): ?... (score: 12.5%)
- **L3.4** (A): ?... (score: 16.7%)
- **L3.6** (A): ?... (score: 12.5%)
- **L3.9** (F): ?... (score: 8.3%)
- **L3.10** (B): ?... (score: 8.3%)
- **L3.12** (G): ?... (score: 0.0%)
- **L3.13** (E): ?... (score: 10.0%)
_... y 14 debilidades mas._

---
_Generado por Vantare Benchmark LLM v1.0_