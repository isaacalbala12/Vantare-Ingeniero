#!/usr/bin/env python3
"""Test MiniMax M2.7 API."""
import httpx, json, sys

api_key = "sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

# Try M2.7 with different formats
models_to_try = [
    'M2.7',
    'MiniMax-M2.7',
    'minimax-m2.7',
    'MiniMaxM2.7',
    'minimax_m2.7',
    'M2.5',
    'minimax_m2',
    'minimax_m',
]

for model in models_to_try:
    print(f"Trying model: {model}...")
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Say hello in one word."}
        ],
        "max_tokens": 10,
    }
    
    try:
        response = httpx.post(
            "https://api.minimaxi.chat/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        data = response.json()
        if response.status_code == 200:
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"  SUCCESS! Model: {model} -> {content}")
            sys.exit(0)
        else:
            error_msg = data.get("error", {}).get("message", "Unknown")
            print(f"  Failed: {error_msg}")
    except Exception as e:
        print(f"  Error: {e}")

print("\nAll models failed.")