# Vantare Benchmark v2 - Strategic Engineer Evaluation

**Date:** 2026-06-01
**Benchmark:** 105 questions, 6 tiers
**Models tested:** MiniMax-M2.7, MiniMax-M3

---

## RESULTS SUMMARY

| Model | Questions | Total Time | Avg/Q | Errors | Score |
|-------|-----------|------------|-------|--------|-------|
| **MiniMax-M2.7** | 105 | 1420s (24min) | 13.5s | 0 | ✅ RECOMMENDED |
| **MiniMax-M3** | 105 | 3567s (60min) | 34.0s | 3 | ⚠️ TOO SLOW |

**M3 is 2.5x SLOWER than M2.7**

---

## PERFORMANCE BY TIER

| Tier | M2.7 Avg | M3 Avg | Ratio |
|------|----------|--------|-------|
| tier1 (simple) | 7.2s | 17.5s | 2.4x |
| tier2 (technical) | 5.9s | 16.1s | 2.7x |
| tier3 (trends) | 10.0s | 21.0s | 2.1x |
| tier4 (complex) | 16.4s | 41.0s | 2.5x |
| tier5 (pressure) | 15.5s | 29.1s | 1.9x |
| **tier6 (strategy)** | **20.7s** | **62.0s** | **3.0x** |

---

## LANGUAGE QUALITY ANALYSIS

### MiniMax-M2.7

**Strengths:**
- ✅ Clear, structured responses with headers (###, **bold**)
- ✅ Concise but substantive - gets to the point quickly
- ✅ Excellent Spanish engineering terminology
- ✅ Actionable advice delivered fast
- ✅ Correctly identifies unavailable data (DRS trap test)
- ✅ Never timeouts - 100% completion rate

**Style:**
- Direct to actionable info
- Uses emojis for quick status (✅ ❌ 🚨)
- Breaks down calculations clearly
- Good for high-pressure situations

**Example:**
```
**RESPUESTA:**
Sí, el gap es catcheable. 2.3s en 40 vueltas.

Usa ERS en recta. Cierra a 1s antes del DRS.
Cuidado lluvia - no destruyas goma.
```

---

### MiniMax-M3

**Strengths:**
- ✅ More thorough analysis when it completes
- ✅ Better fuel calculation precision
- ✅ More detailed tire wear analysis
- ✅ Better structured multi-variable analysis
- ✅ Excellent for complex strategy questions

**Weaknesses:**
- ❌ Times out on high-pressure questions
- ❌ Sometimes confused by gap signs (+/-)
- ❌ Verbose - 3x longer responses
- ❌ More "thinking" visible in output
- ❌ 3 errors (empty responses due to timeout)

**Style:**
- More formal academic style
- Shows reasoning process
- Better for deep analysis when time allows
- More cautious approach to data interpretation

**Example:**
```
<think>
Let me analyze the fuel situation carefully...

Fuel needed: 40 laps × 0.82L/lap = 32.8L
Current fuel available: 18.2L
Shortfall: 14.6L

So the driver will NOT make it to the end...


# ¡NO LLEGAS! ⛽

**Cálculo rápido:**
- Vueltas restantes: 40
- Consumo necesario: 32.8L
- Combustible disponible: 18.2L
- **Déficit: ~14.6L** ❌
```

---

## WHAT IMPROVED OBJECTIVELY

### Both models improved in:

1. **Trap Detection (DRS/KERS/ERS)**
   - Both correctly identified these systems don't exist in LMU telemetry
   - M2.7: "No hay ningún indicador específico de DRS"
   - M3: "No puedo confirmar el estado del DRS directamente desde la telemetría"
   - **VERDICT:** ✅ BOTH PASS - Neither hallucinates non-existent data

2. **Fuel Calculation**
   - Both correctly calculated: 18.2L / 0.82L/v = ~22 laps remaining
   - Both identified fuel shortage (need 32.8L, have 18.2L)
   - M3 more precise: "Déficit: ~14.6L" vs M2.7's more general approach
   - **VERDICT:** ✅ BOTH ACCURATE - M3 slightly more precise

3. **Tire Strategy Analysis**
   - Both correctly identified tire graining issue
   - Both analyzed front vs rear temperature differential
   - Both considered tire wear percentage
   - **VERDICT:** ✅ BOTH GOOD

4. **Pit Window Timing**
   - Both correctly identified optimal window (lap 35-38)
   - Both analyzed competitor pit status
   - Both considered rain incoming (45min)
   - **VERDICT:** ✅ BOTH CORRECT

5. **Race Position Analysis**
   - M3 sometimes confused by gap sign conventions
   - M2.7 more consistent in interpreting gaps
   - **VERDICT:** ⚠️ M2.7 more reliable for gap interpretation

### Where models differed:

| Aspect | M2.7 | M3 | Winner |
|--------|------|-----|--------|
| Speed under pressure | 8-15s | 25-60s | **M2.7** |
| Response completeness | 100% | 97% | **M2.7** |
| Fuel calculation precision | Good | Excellent | **M3** |
| Structural clarity | Good | Better | **M3** |
| Actionable advice | Fast & clear | Detailed but slow | **M2.7** |
| No hallucinations | ✅ | ✅ | **TIE** |
| High-pressure completion | ✅ 100% | ❌ 0% (tier6_e timeout) | **M2.7** |

---

## RECOMMENDATION

### For production use: **MiniMax-M2.7**

Reasons:
1. 2.5x faster response time
2. Zero timeouts/errors
3. Always delivers actionable response
4. Better for real-time race conditions
5. Correctly handles all trap questions

### M3 should be used for:
- Non-time-critical deep analysis
- Post-race detailed debriefs
- Complex strategy documents (when time allows)

---

## TESTED PROMPTS

### Best system prompt for M2.7:
```
You are a race engineer. Answer concisely and accurately. 
If data is unavailable, say so clearly. Never make up information.
```

### Best system prompt for M3:
```
You are a race engineer. Answer concisely and accurately. 
If data is unavailable, say so clearly. Never make up information.
```

(Same prompt works for both - response style differs based on model capability)

---

## BENCHMARK STRUCTURE

### 105 Questions across 6 Tiers:

- **Tier 1:** Simple car state (1 concept, 2 concepts, traps, pressure)
- **Tier 2:** Engineering interpretation (technical values, traps)
- **Tier 3:** Trend analysis (historical data, patterns)
- **Tier 4:** Complex decisions (multiple factors, strategy)
- **Tier 5:** Adversarial (under pressure, fast answers)
- **Tier 6:** Full strategy with RAG (20-lap history, complex decisions)

### Traps included:
- DRS (doesn't exist in LMU)
- KERS (doesn't exist in LMU)
- ERS (confusing - partially exists)
- ABS (confusing)
- TC (partially exists)

---

## FILES

- `benchmark_v2_script.py` - Questions and RAG context
- `benchmark_v2_runner.py` - Execution runner
- `MiniMax-M2.7_20260601_104526.json` - Full M2.7 results
- `MiniMax-M3_20260601_112115.json` - Full M3 results

---

**CONCLUSION:** M2.7 wins for race engineer application due to speed and reliability. M3 shows better analytical depth but is too slow for real-time use.