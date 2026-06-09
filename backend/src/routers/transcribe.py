import logging

from fastapi import APIRouter, File, UploadFile

logger = logging.getLogger("vantare.transcribe")

router = APIRouter()


@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Endpoint placeholder for ASR transcription of WAV audio.

    Currently returns empty text. Future integration:
    - Local Whisper (faster-whisper)
    - Cloud API (Deepgram, Azure Speech)
    """
    logger.info("Received audio for transcription: %s (%s)", audio.filename, audio.content_type)

    # Read the audio (placeholder — no transcription yet)
    _ = await audio.read()

    return {"text": ""}
