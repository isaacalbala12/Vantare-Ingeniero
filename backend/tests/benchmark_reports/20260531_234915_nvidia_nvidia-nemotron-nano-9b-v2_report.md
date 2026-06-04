# Benchmark LLM: nvidia_nvidia-nemotron-nano-9b-v2

- **Endpoint**: http://192.168.1.41:1234
- **Modelo**: nvidia_nvidia-nemotron-nano-9b-v2
- **Fecha**: 2026-05-31 23:49
- **Duracion total**: 1357s
- **Total prompts**: 140

## Resultados por Nivel

| Nivel | Nombre | Pts | Prompts | Aciertos | Aprobado | TTFT(ms) | Tok/s |
|-------|--------|:---:|:-------:|:--------:|:--------:|:--------:|:-----:|
| L1 | Extraccion de campos | 74.5% | 31 | 27/31 | NO PASA | 4961ms | 5.5 |
| L2 | Interpretacion de campos | 65.1% | 20 | 18/20 | NO PASA | 8125ms | 8.6 |
| L3 | Respuesta a triggers | 25.8% | 19 | 3/19 | NO PASA | 10558ms | 12.0 |
| L4 | Razonamiento multicampo | 44.4% | 20 | 13/20 | NO PASA | 8011ms | 12.1 |
| L5 | Razonamiento con RAG | 39.8% | 15 | 8/15 | NO PASA | 10359ms | 9.8 |
| L6 | Estrategia multi-trigger | 34.8% | 10 | 4/10 | NO PASA | 9008ms | 10.7 |
| L7 | Casos limite y anomalias | 51.9% | 15 | 9/15 | NO PASA | 7018ms | 10.0 |
| L8 | Razonamiento temporal | 25.2% | 10 | 5/10 | PASA | 12920ms | 12.3 |

## Resumen Global

- **Nivel maximo aprobado**: L8
- **Prompts totales**: 140
- **Aciertos totales**: 87/140 (62.1%)
- **Puntuacion ponderada (por nivel)**: 39.8%

## Matriz de Aprobacion

```
L1 [##############------] 74.5% (min 90.0%) X
L2 [#############-------] 65.1% (min 85.0%) X
L3 [#####---------------] 25.8% (min 80.0%) X
L4 [########------------] 44.4% (min 75.0%) X
L5 [#######-------------] 39.8% (min 70.0%) X
L6 [######--------------] 34.8% (min 65.0%) X
L7 [##########----------] 51.9% (min 60.0%) X
L8 [#####---------------] 25.2% (min 0.0%) >
```

## Debilidades Detectadas

- **L1.6** (A): ?... (score: 0.0%)
- **L1.13** (A): ?... (score: 0.0%)
- **L1.30** (F): ?... (score: 0.0%)
- **L3.2** (A): ?... (score: 12.5%)
- **L3.3** (C): ?... (score: 0.0%)
- **L3.9** (F): ?... (score: 16.7%)
- **L3.13** (E): ?... (score: 10.0%)
- **L3.14** (C): ?... (score: 12.5%)
- **L3.17** (A): ?... (score: 12.5%)
- **L3.19** (C): ?... (score: 8.3%)
_... y 11 debilidades mas._

---
_Generado por Vantare Benchmark LLM v1.0_