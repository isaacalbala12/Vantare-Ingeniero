"""Quita razonamiento interno del LLM antes de TTS / WebSocket."""

from __future__ import annotations

import re

_THINK_BLOCK = re.compile(r"<think\b[^>]*>.*?</think>", re.DOTALL | re.IGNORECASE)
_REASONING_LINE = re.compile(
    r"^\s*(wait[,.!]?|el usuario|no tengo que|no debo|revisa la pregunta|"
    r"así que la respuesta|no genero|no emitir|se respeta la solicitud|por favor, no digas)\b",
    re.IGNORECASE | re.MULTILINE,
)


def sanitize_llm_speech(text: str) -> str:
    """Devuelve solo texto apto para radio (sin chain-of-thought)."""
    if not text or not text.strip():
        return ""

    cleaned = _THINK_BLOCK.sub("", text)
    cleaned = re.sub(r"</?think[^>]*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()

    if not cleaned:
        return ""

    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    kept: list[str] = []
    for ln in lines:
        if _REASONING_LINE.match(ln):
            continue
        if re.search(r"\b(wait|reasoning|chain of thought)\b", ln, re.IGNORECASE):
            continue
        kept.append(ln)

    if kept:
        cleaned = " ".join(kept)
    else:
        cleaned = ""

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > 500:
        cleaned = cleaned[:497].rstrip() + "..."
    return cleaned
