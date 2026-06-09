"""Quita razonamiento interno del LLM antes de TTS / WebSocket."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Bloques XML/HTML de chain-of-thought (Qwen, Stepfun, DeepSeek, etc.)
_THINK_TAGS = ("think", "redacted_thinking", "thinking", "reasoning")
_ORPHAN_TAG = re.compile(
    r"</?(?:" + "|".join(_THINK_TAGS) + r")(?:\s[^>]*)?>",
    re.IGNORECASE,
)

# Líneas meta que no deben leerse en radio
_REASONING_LINE = re.compile(
    r"^\s*("
    r"wait[,.!?]?|"
    r"el usuario|el piloto|la pregunta|debo|no debo|no tengo que|"
    r"así que la respuesta|no genero|no emitir|se respeta|por favor,? no digas|"
    r"revisa la pregunta|analicemos|primero,? |primero voy|voy a |necesito |"
    r"según el contexto|basándome en|let me |the user |i need to |"
    r"first,? i |based on the |chain of thought|reasoning"
    r")\b",
    re.IGNORECASE | re.MULTILINE,
)

# Prefijos típicos de meta-respuesta antes del texto de radio
_META_PREFIX = re.compile(
    r"^(?:"
    r"(?:el usuario|the user)[^.!\n]{0,120}[.!]\s*|"
    r"(?:debo|i should|i need to)[^.!\n]{0,120}[.!]\s*|"
    r"(?:wait|espera)[,.!?]\s*|"
    r"(?:primero,? )[^.!\n]{0,120}[.!]\s*"
    r")+",
    re.IGNORECASE | re.DOTALL,
)

_REASONING_BLOB = re.compile(
    r"\b(algo como|wait,?|oh,? right|quiz[aá]s|m[aá]s corta|el tono de radio|s[ií], es)\b",
    re.IGNORECASE,
)

_TICKER_LINE = re.compile(
    r"^(?:DRV:|GAP(?:>|$)|BRK:|TYR:|P\d+\|L\d|FCY:|PIT:|WEATHER:|\|)",
    re.IGNORECASE,
)


@dataclass
class SpeechSanitizeState:
    """Estado opcional para streaming incremental."""

    last_spoken: str = ""


def _open_tag_pattern(tag: str) -> str:
    return rf"<{re.escape(tag)}(?:\s[^>]*)?>"


def _close_tag_pattern(tag: str) -> str:
    return rf"</{re.escape(tag)}\s*>"


def _strip_think_blocks(text: str) -> str:
    cleaned = text

    # Truncar antes de cualquier bloque abierto sin cerrar (stream en curso)
    earliest_cut = len(cleaned)
    for tag in _THINK_TAGS:
        open_re = re.compile(_open_tag_pattern(tag), re.IGNORECASE)
        close_re = re.compile(_close_tag_pattern(tag), re.IGNORECASE)
        for m in open_re.finditer(cleaned):
            if not close_re.search(cleaned[m.end() :]):
                earliest_cut = min(earliest_cut, m.start())
    if earliest_cut < len(cleaned):
        cleaned = cleaned[:earliest_cut]

    for tag in _THINK_TAGS:
        block = re.compile(
            _open_tag_pattern(tag) + r".*?" + _close_tag_pattern(tag),
            re.DOTALL | re.IGNORECASE,
        )
        cleaned = block.sub("", cleaned)
    cleaned = _ORPHAN_TAG.sub("", cleaned)
    return cleaned


def _is_reasoning_line(line: str) -> bool:
    if _TICKER_LINE.match(line.strip()):
        return True
    if _REASONING_LINE.match(line):
        return True
    if re.search(r"\b(chain of thought|reasoning|meta-commentary)\b", line, re.IGNORECASE):
        return True
    return False


def _looks_like_reasoning_blob(text: str) -> bool:
    if not text:
        return False
    if _is_reasoning_line(text):
        return True
    return bool(_REASONING_BLOB.search(text))


def _pick_radio_body(text: str) -> str:
    """Si hay varios párrafos, prioriza el último que no parezca razonamiento."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(parts) <= 1:
        return text.strip()
    for part in reversed(parts):
        if not _is_reasoning_line(part) and len(part) <= 400:
            return part
    for part in reversed(parts):
        if not _is_reasoning_line(part):
            return part
    return parts[-1]

def _extract_quoted_radio(text: str) -> str:
    """Extrae la última frase entre comillas cuando el modelo razona en voz alta."""
    candidates: list[str] = []
    for match in re.finditer(r'"([^"\n]{8,400})"|«([^»\n]{8,400})»', text):
        snippet = (match.group(1) or match.group(2) or "").strip()
        if not snippet or _is_reasoning_line(snippet):
            continue
        if re.match(r"^(?:el usuario|the user|wait|espera)\b", snippet, re.IGNORECASE):
            continue
        if _TICKER_LINE.match(snippet):
            continue
        candidates.append(snippet)
    if candidates:
        return candidates[-1]
    return ""


def _collapse_duplicate_quoted_blocks(text: str) -> str:
    """Si el modelo emitió varias versiones entre comillas, conserva solo la última."""
    matches = list(re.finditer(r'"([^"\n]{8,400})"|«([^»\n]{8,400})»', text))
    if len(matches) >= 2:
        last = matches[-1]
        return (last.group(1) or last.group(2) or "").strip()
    return text


def _strip_wrapping_quotes(text: str) -> str:
    cleaned = text.strip()
    while len(cleaned) >= 2 and cleaned[0] in "\"'«»" and cleaned[-1] in "\"'«»":
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _cap_radio_sentences(text: str, max_sentences: int = 2) -> str:
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    if len(parts) <= max_sentences:
        return text.strip()
    return " ".join(parts[:max_sentences]).strip()


def sanitize_llm_speech(text: str, *, finalize: bool = True) -> str:
    """Devuelve solo texto apto para radio (sin chain-of-thought)."""
    if not text:
        return ""

    cleaned = _strip_think_blocks(text)
    cleaned = _ORPHAN_TAG.sub("", cleaned)
    cleaned = re.sub(r"<\|[^|]+\|>", "", cleaned)
    if re.search(r"<tool_call>|<function=", cleaned, re.IGNORECASE):
        if finalize:
            quoted = _extract_quoted_radio(text)
            return quoted
        return ""

    if not finalize:
        # En stream: no emitir razonamiento ni bloques entre comillas incompletos.
        partial = _strip_wrapping_quotes(cleaned.strip())
        if _looks_like_reasoning_blob(partial):
            return ""
        return partial

    collapsed = _collapse_duplicate_quoted_blocks(cleaned)
    if collapsed != cleaned and collapsed:
        cleaned = collapsed

    cleaned = _META_PREFIX.sub("", cleaned.strip())
    if not cleaned:
        return ""

    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    kept: list[str] = []
    for ln in lines:
        if _is_reasoning_line(ln):
            continue
        kept.append(ln)

    if kept:
        cleaned = _pick_radio_body("\n".join(kept))
    else:
        cleaned = ""

    quoted = _extract_quoted_radio(text)
    if finalize and quoted and (not cleaned or _looks_like_reasoning_blob(cleaned)):
        cleaned = quoted
    elif finalize and not cleaned:
        cleaned = quoted

    if finalize:
        cleaned = _strip_wrapping_quotes(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = _cap_radio_sentences(cleaned, max_sentences=2)
        if len(cleaned) > 320:
            cleaned = cleaned[:317].rstrip() + "..."
    return cleaned


def sanitize_llm_speech_delta(
    full_raw: str,
    state: SpeechSanitizeState | None = None,
    *,
    finalize: bool = False,
) -> tuple[str, str]:
    """Dado texto acumulado del stream, devuelve (spoken_full, delta_nuevo)."""
    spoken = sanitize_llm_speech(full_raw, finalize=finalize)
    prev = state.last_spoken if state else ""
    if spoken.startswith(prev):
        delta = spoken[len(prev) :]
    else:
        delta = spoken
    if state is not None:
        state.last_spoken = spoken
    return spoken, delta
