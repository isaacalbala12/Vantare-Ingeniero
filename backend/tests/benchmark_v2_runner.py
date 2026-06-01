#!/usr/bin/env python3
"""
Vantare Benchmark v2 - Runner

Ejecuta las 105 preguntas contra los modelos y guarda respuestas
para evaluacion humana + LLM judge.
"""

import httpx, json, time, sys, os
from datetime import datetime

# Import from benchmark script
from benchmark_v2_script import QUESTIONS, RAG_CONTEXT, SYSTEM_PROMPT

# =============================================================================
# CONFIG
# =============================================================================

MODELS = [
    {
        "name": "MiniMax-M2.7",
        "base_url": "https://api.minimaxi.chat/v1",
        "model": "MiniMax-M2.7",
        "api_key": "sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0",
        "max_tokens": 8000,
        "temperature": 0.3,
    },
    {
        "name": "MiniMax-M3",
        "base_url": "https://api.minimaxi.chat/v1",
        "model": "MiniMax-M3",
        "api_key": "sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0",
        "max_tokens": 8000,
        "temperature": 0.3,
    },
    {
        "name": "StepFun-3.7",
        "base_url": "https://api.stepfun.ai/step_plan/v1",
        "model": "step-3.7-flash",
        "api_key": "5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo",
        "max_tokens": 8000,
        "temperature": 0.1,
        "thinking": "disabled",
    },
]

# =============================================================================
# SIMPLE TELEMETRY CONTEXT for tiers 1-5
# =============================================================================

SIMPLE_CONTEXT = """TELEMETRIA ACTUAL:
Position: P3 | Lap: 25/65 | Gap P2: +2.341s | Gap P4: -4.127s
Fuel: 18.2L | Consumption: 0.82L/v | Battery: 0.72
RPM: 8472 | Throttle: 85% | Brake: 62% | Gear: 6
FL_Tyre: 89C | FR_Tyre: 87C | RL_Tyre: 78C | RR_Tyre: 76C
FL_Brake: 342C | FR_Brake: 338C | RL_Brake: 298C | RR_Brake: 295C
Oil_Temp: 102C | Water_Temp: 94C
Suspension: FL 0.038m | FR 0.036m | RL 0.041m | RR 0.039m
RideHeight: 0.072m | Drag: 0.98 | Downforce: F825N R1120N
TC: OFF | ABS: OFF | ERS: Active | ERS_Torque: 145Nm
TireCompound: Medium | LastLap: 1:32.847 | BestLap: 1:31.234
Weather: LightRain 70% | TrackTemp: 28C | Ambient: 22C
"""

# =============================================================================
# API CALL
# =============================================================================

def call_model(model_config, messages, timeout=120):
    """Llama a un modelo y devuelve la respuesta."""
    headers = {
        "Authorization": f"Bearer {model_config['api_key']}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model_config["model"],
        "messages": messages,
        "max_tokens": model_config["max_tokens"],
        "temperature": model_config["temperature"],
    }
    
    # StepFun-specific
    if "stepfun" in model_config["base_url"]:
        payload["thinking"] = {"type": model_config.get("thinking", "disabled")}
    
    try:
        r = httpx.post(
            f"{model_config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}", "text": r.text[:500]}
        
        data = r.json()
        
        # Extract response
        content = data["choices"][0]["message"].get("content", "")
        reasoning = data["choices"][0]["message"].get("reasoning", "")
        
        # Use content if available, otherwise use reasoning (for thinking models)
        text = content if content.strip() else reasoning
        
        return {"text": text.strip(), "raw": data}
        
    except Exception as e:
        return {"error": str(e), "text": ""}

# =============================================================================
# BUILD MESSAGES
# =============================================================================

def build_messages(tier, question, include_rag=False):
    """Construye mensajes para la peticion."""
    
    # Select context
    if tier == "tier6" or include_rag:
        context = RAG_CONTEXT
    else:
        context = SIMPLE_CONTEXT
    
    system = f"""You are a race engineer assistant for a racing driver. 
Answer the driver's question concisely and accurately.
If data is not available in the telemetry, say so clearly.
Never make up information.

{SYSTEM_PROMPT}"""

    user = f"""{context}

PILOTO: {question}"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

# =============================================================================
# RUN BENCHMARK
# =============================================================================

def run_benchmark(model_config, questions=None, start_idx=0, end_idx=None, verbose=True):
    """Ejecuta el benchmark para un modelo."""
    
    if questions is None:
        questions = QUESTIONS
    
    if end_idx is None:
        end_idx = len(questions)
    
    results = []
    total_time = 0
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"BENCHMARK: {model_config['name']}")
        print(f"Questions: {start_idx+1} to {end_idx}")
        print(f"{'='*60}\n")
    
    for i, (tier, level, question) in enumerate(questions[start_idx:end_idx], start=start_idx):
        idx = i + 1
        
        # Build messages
        include_rag = (tier == "tier6")
        messages = build_messages(tier, question, include_rag)
        
        # Call model
        start_time = time.time()
        response = call_model(model_config, messages)
        elapsed = time.time() - start_time
        total_time += elapsed
        
        # Store result
        result = {
            "idx": idx,
            "tier": tier,
            "level": level,
            "question": question,
            "response": response.get("text", ""),
            "error": response.get("error", ""),
            "elapsed": elapsed,
        }
        results.append(result)
        
        # Print progress
        if verbose:
            short_resp = response.get("text", response.get("error", ""))[:80].replace("\n", " ")
            print(f"[{idx:3d}/{end_idx}] {tier}_{level}: {short_resp}... ({elapsed:.1f}s)")
        
        # Rate limiting
        time.sleep(0.5)
    
    if verbose:
        print(f"\nCompleted in {total_time:.1f}s ({total_time/len(results):.1f}s avg)")
    
    return results

# =============================================================================
# SAVE RESULTS
# =============================================================================

def save_results(results, model_name, output_dir="benchmark_results"):
    """Guarda resultados en JSON y MD."""
    
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON
    json_path = os.path.join(output_dir, f"{model_name}_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "model": model_name,
            "timestamp": timestamp,
            "total": len(results),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    
    # Markdown report
    md_path = os.path.join(output_dir, f"{model_name}_{timestamp}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Benchmark Results: {model_name}\n\n")
        f.write(f"**Date:** {timestamp}\n\n")
        f.write(f"**Total Questions:** {len(results)}\n\n")
        f.write("---\n\n")
        
        current_tier = None
        for r in results:
            if r["tier"] != current_tier:
                current_tier = r["tier"]
                f.write(f"\n## {current_tier.upper()}\n\n")
            
            f.write(f"### Q{r['idx']}: {r['question']}\n\n")
            f.write(f"**Level:** {r['level']} | **Time:** {r['elapsed']:.1f}s\n\n")
            
            if r["error"]:
                f.write(f"**ERROR:** {r['error']}\n\n")
            else:
                f.write(f"**Response:**\n```\n{r['response']}\n```\n\n")
            
            f.write("---\n\n")
    
    print(f"\nSaved: {json_path}")
    print(f"Saved: {md_path}")
    
    return json_path, md_path

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Parse arguments
    model_name = sys.argv[1] if len(sys.argv) > 1 else None
    start_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    end_idx = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    if model_name:
        # Run specific model
        model_config = next((m for m in MODELS if m["name"] == model_name), None)
        if not model_config:
            print(f"Unknown model: {model_name}")
            print(f"Available: {[m['name'] for m in MODELS]}")
            sys.exit(1)
        
        results = run_benchmark(model_config, start_idx=start_idx, end_idx=end_idx)
        save_results(results, model_config["name"])
    else:
        # Run all models
        for model_config in MODELS:
            print(f"\n\n{'#'*60}")
            print(f"# Running: {model_config['name']}")
            print(f"{'#'*60}")
            
            results = run_benchmark(model_config, start_idx=start_idx, end_idx=end_idx)
            save_results(results, model_config["name"])
            
            print(f"\n>>> {model_config['name']} DONE. Next model in 5s...")
            time.sleep(5)
