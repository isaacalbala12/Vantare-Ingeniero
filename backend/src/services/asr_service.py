from __future__ import annotations

import logging
import os
import tempfile
import threading
from typing import Literal, Optional

logger = logging.getLogger("vantare.asr")

_model = None
_load_error: Optional[str] = None
_loading = False
_load_lock = threading.Lock()

WhisperPreloadMode = Literal["startup", "first_question"]


def _whisper_settings():
    try:
        from src.config import settings

        return (
            settings.WHISPER_MODEL,
            settings.WHISPER_DEVICE,
            settings.WHISPER_COMPUTE_TYPE,
            settings.WHISPER_PRELOAD.lower(),
        )
    except Exception:
        return (
            os.getenv("WHISPER_MODEL", "small"),
            os.getenv("WHISPER_DEVICE", "cpu"),
            os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
            os.getenv("WHISPER_PRELOAD", "startup").lower(),
        )


def get_asr_status() -> dict:
    """Estado ASR para /health y diagnóstico."""
    _, _, _, preload_mode = _whisper_settings()
    if _model is not None:
        state = "ready"
    elif _loading:
        state = "loading"
    elif _load_error:
        state = "error"
    else:
        state = "idle"
    model_name, device, compute_type, _ = _whisper_settings()
    return {
        "state": state,
        "preload_mode": preload_mode,
        "model": model_name,
        "device": device,
        "compute_type": compute_type,
        "error": _load_error,
    }


def preload_whisper() -> bool:
    """Carga el modelo Whisper (bloqueante — usar en thread/async.to_thread)."""
    global _loading
    with _load_lock:
        if _model is not None:
            return True
        if _load_error is not None:
            return False
        _loading = True
    try:
        model = _load_model_sync()
        return model is not None
    finally:
        with _load_lock:
            _loading = False


def _load_model_sync():
    global _model, _load_error
    if _model is not None:
        return _model
    if _load_error is not None:
        return None
    model_name, device, compute_type, _ = _whisper_settings()
    try:
        from faster_whisper import WhisperModel

        logger.info("Cargando Whisper %s (%s, %s)", model_name, device, compute_type)
        _model = WhisperModel(model_name, device=device, compute_type=compute_type)
        logger.info("Whisper ASR listo (%s)", model_name)
        return _model
    except Exception as exc:
        _load_error = str(exc)
        logger.error("No se pudo cargar faster-whisper: %s", exc)
        return None


def _get_model():
    return _load_model_sync()


def transcribe_wav(data: bytes, *, language: str = "es") -> str:
    """Transcribe WAV/PCM bytes a texto (español por defecto)."""
    if not data or len(data) < 100:
        return ""

    model = _get_model()
    if model is None:
        return ""

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        segments, _info = model.transcribe(
            tmp_path,
            language=language,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()
        logger.info("ASR: %d bytes → %r", len(data), text[:160])
        return text
    except Exception as exc:
        logger.error("ASR transcribe falló: %s", exc, exc_info=True)
        return ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def reset_asr_for_tests() -> None:
    """Solo tests — reinicia singleton."""
    global _model, _load_error, _loading
    with _load_lock:
        _model = None
        _load_error = None
        _loading = False
