# Benchmark LLM: nvidia/nemotron-3-nano-4b

- **Endpoint**: http://192.168.1.41:1234
- **Modelo**: nvidia/nemotron-3-nano-4b
- **Fecha**: 2026-05-31 18:41
- **Duracion total**: 358s
- **Total prompts**: 140

## Resultados por Nivel

| Nivel | Nombre | Pts | Prompts | Aciertos | Aprobado | TTFT(ms) | Tok/s |
|-------|--------|:---:|:-------:|:--------:|:--------:|:--------:|:-----:|
| L1 | Extraccion de campos | 32.0% | 31 | 13/31 | NO PASA | 1329ms | 10.9 |
| L2 | Interpretacion de campos | 36.6% | 20 | 9/20 | NO PASA | 1530ms | 19.2 |
| L3 | Respuesta a triggers | 12.1% | 19 | 1/19 | NO PASA | 2315ms | 22.7 |
| L4 | Razonamiento multicampo | 31.8% | 20 | 10/20 | NO PASA | 2514ms | 18.8 |
| L5 | Razonamiento con RAG | 28.5% | 15 | 6/15 | NO PASA | 3090ms | 16.6 |
| L6 | Estrategia multi-trigger | 24.2% | 10 | 2/10 | NO PASA | 1798ms | 22.5 |
| L7 | Casos limite y anomalias | 21.7% | 15 | 5/15 | NO PASA | 2336ms | 16.1 |
| L8 | Razonamiento temporal | 21.8% | 10 | 3/10 | PASA | 2901ms | 18.7 |

## Resumen Global

- **Nivel maximo aprobado**: L8
- **Prompts totales**: 140
- **Aciertos totales**: 49/140 (35.0%)
- **Puntuacion ponderada (por nivel)**: 24.5%

## Matriz de Aprobacion

```
L1 [######--------------] 32.0% (min 90.0%) X
L2 [#######-------------] 36.6% (min 85.0%) X
L3 [##------------------] 12.1% (min 80.0%) X
L4 [######--------------] 31.8% (min 75.0%) X
L5 [#####---------------] 28.5% (min 70.0%) X
L6 [####----------------] 24.2% (min 65.0%) X
L7 [####----------------] 21.7% (min 60.0%) X
L8 [####----------------] 21.8% (min 0.0%) >
```

## Debilidades Detectadas

- **L1.1** (A): ?... (score: 0.0%)
- **L1.2** (A): ?... (score: 0.0%)
- **L1.3** (A): ?... (score: 0.0%)
- **L1.10** (A): ?... (score: 0.0%)
- **L1.11** (A): ?... (score: 0.0%)
- **L1.12** (A): ?... (score: 0.0%)
- **L1.13** (A): ?... (score: 0.0%)
- **L1.14** (A): ?... (score: 0.0%)
- **L1.15** (A): ?... (score: 0.0%)
- **L1.17** (B): ?... (score: 0.0%)
_... y 50 debilidades mas._

---
_Generado por Vantare Benchmark LLM v1.0_