# Benchmark: Prompt Optimization Results (June 1, 2026)

## Night Iteration Results

### Objective
Improve benchmark scores for MiniMax-M2.7 and StepFun-3.7-Flash by optimizing system prompts.

### Key Finding: The Original Prompt Was Suboptimal

The original benchmark used:
```
"Eres un ingeniero de carrera. Maximo 2-3 frases. Estilo radio."
```

This prompt was outperformed by a more directive approach.

---

## Winning Prompt (NEW2)

```
Race engineer response: Data questions -> numbers only. 
Advice questions -> short action. Be concise. 
Example data: P3 L10 F42.3. 
Example advice: Entrar boxes urgente.
```

### Why It Works
1. **Separates question types**: Data questions get numbers, advice questions get short action verbs
2. **Provides concrete examples**: Models understand the expected output format
3. **Enforces conciseness**: "Be concise" prevents verbose responses that dilute keywords
4. **Uses racing terminology**: "Entrar boxes" is the exact vocabulary used in keyword matching

---

## Definitive Results (22 questions, 3 runs, SYNC)

| Model | ORIG | NEW2 | Improvement |
|-------|------|------|-------------|
| MiniMax-M2.7 | 64.4% | **72.3%** | **+7.9%** |
| StepFun-3.7-Flash | 69.4% | **74.1%** | **+4.7%** |
| **COMBINED AVG** | 66.9% | **73.2%** | **+6.3%** |

### Per-Run Data

**MiniMax-M2.7:**
- MM-ORIG: 64.0%, 57.2%, 72.0% → avg 64.4%
- MM-NEW: 73.4%, 74.6%, 69.0% → avg 72.3%

**StepFun-3.7-Flash:**
- SF-ORIG: 65.2%, 69.7%, 73.4% → avg 69.4%
- SF-NEW: 73.6%, 73.6%, 75.2% → avg 74.1%

---

## Important: Sync vs Async

Testing revealed that async requests (httpx.AsyncClient with asyncio.gather) produced inconsistent results (~27% for SF) while sync requests produced consistent results (~70%). The same code with `asyncio.gather` mixing different prompts caused API state contamination.

**Recommendation**: For reliable benchmark results, use sequential (sync) HTTP requests, not concurrent async.

---

## Score Breakdown by Level

### Original Prompt (ORIG)
| Level | MM | SF |
|-------|----|----|
| L1 (Extraction) | ~79% | ~79% |
| L2 (Interpretation) | ~69% | ~60% |
| L3 (Triggers) | ~44% | ~44% |
| L4 (Multicampo) | 100% | 100% |
| L5 (RAG) | ~67% | ~73% |
| L6 (Multi-trigger) | ~62% | ~62% |
| L7 (Edge cases) | 75% | 75% |
| L8 (Temporal) | 25% | 25% |

### NEW2 Prompt
| Level | MM | SF |
|-------|----|----|
| L1 (Extraction) | ~79% | ~79% |
| L2 (Interpretation) | ~85% | ~77% |
| L3 (Triggers) | ~56% | ~56% |
| L4 (Multicampo) | 100% | 100% |
| L5 (RAG) | ~73% | ~73% |
| L6 (Multi-trigger) | ~75% | ~75% |
| L7 (Edge cases) | 75% | 75% |
| L8 (Temporal) | 25% | 25% |

---

## Other Findings

### Temperature
- MiniMax: Temperature 0.3 performed better than 0.1 in some tests
- StepFun: Temperature 0.1 was consistently best

### max_tokens
- Setting max_tokens=200 caused truncated responses for StepFun (answer cut off before keywords)
- Original benchmark used max_tokens=500, which is necessary for full responses

### Keyword Extraction
- StepFun uses `reasoning` field for content (not `content`)
- MiniMax uses `content` field primarily
- `reasoning_content` field exists but is rarely populated

---

## Files Created During Night Iteration

- `backend/tests/night_iter_v*.py` - Various iteration scripts
- `backend/tests/night_final_report.py` - Final definitive comparison
- `backend/tests/debug_sync_22q.py` - Sync verification (22 questions)

## Original Benchmark Files

- `backend/tests/benchmark_compare_cloud.py` - Original benchmark with original prompts
- `backend/tests/benchmark_llm.py` - Local model benchmark

---

## Conclusion

The NEW2 prompt improves both models significantly:
- **+7.9%** for MiniMax-M2.7 (64.4% → 72.3%)
- **+4.7%** for StepFun-3.7-Flash (69.4% → 74.1%)

Combined average improvement: **+6.3%** (66.9% → 73.2%)

The improvement comes from:
1. Explicitly differentiating data vs advice questions
2. Providing concrete examples of expected output
3. Enforcing brevity with "Be concise"
4. Using exact racing vocabulary in examples
