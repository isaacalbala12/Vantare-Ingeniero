import asyncio
import io
import json
import logging
import wave
from pathlib import Path

import numpy as np
import onnxruntime as ort

logger = logging.getLogger("vantare.tts")


class TTSService:
    """Servicio de síntesis de voz usando Piper TTS (ONNX, CPU ligero).

    Usa piper-onnx internamente pero con manejo correcto de encoding UTF-8
    para los archivos de configuración en Windows.
    """

    def __init__(self, model_path: str) -> None:
        self._model_path = Path(model_path)
        if not self._model_path.exists():
            raise FileNotFoundError(f"Modelo TTS no encontrado: {model_path}")

        config_path = self._model_path.with_suffix(".onnx.json")
        if not config_path.exists():
            raise FileNotFoundError(f"Config TTS no encontrado: {config_path}")

        # Cargar config con encoding UTF-8 explícito
        with open(str(config_path), "r", encoding="utf-8") as f:
            self._config: dict = json.load(f)

        self.sample_rate: int = self._config["audio"]["sample_rate"]
        self._phoneme_id_map: dict = self._config["phoneme_id_map"]
        self._voices: dict = self._config.get("speaker_id_map", {})

        # Inicializar sesión ONNX
        opts = ort.SessionOptions()
        # Reducir hilos para no impactar al simulador en CPU
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        self._sess = ort.InferenceSession(
            str(self._model_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        self._sess_inputs = [i.name for i in self._sess.get_inputs()]

        logger.info(
            "Modelo TTS cargado: rate=%dHz, speakers=%d",
            self.sample_rate,
            len(self._voices),
        )

    async def synthesize(self, text: str) -> bytes:
        """
        Sintetiza texto a audio WAV.
        Se ejecuta en un thread pool para no bloquear el event loop.
        Devuelve bytes en formato WAV (PCM 16-bit mono, sample_rate Hz).
        """
        if not text or not text.strip():
            return b""

        loop = asyncio.get_running_loop()
        wav_bytes = await loop.run_in_executor(None, self._synthesize_sync, text)
        return wav_bytes

    # ------------------------------------------------------------------
    # Lógica síncrona (corre en thread pool)
    # ------------------------------------------------------------------

    _BOS = "^"
    _EOS = "$"
    _PAD = "_"

    def _phoneme_to_ids(self, phonemes: list[str]) -> list[int]:
        ids: list[int] = []
        for p in phonemes:
            if p in self._phoneme_id_map:
                ids.extend(self._phoneme_id_map[p])
                ids.extend(self._phoneme_id_map[self._PAD])
        ids.extend(self._phoneme_id_map[self._EOS])
        return ids

    def _synthesize_sync(self, text: str) -> bytes:
        """Síncrono: fonemiza -> ONNX inference -> empaqueta WAV."""
        # Import perezoso de phonemizer (solo se importa cuando se usa TTS)
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
        from phonemizer import phonemize
        import espeakng_loader

        EspeakWrapper.set_library(espeakng_loader.get_library_path())
        EspeakWrapper.set_data_path(espeakng_loader.get_data_path())

        # Fonemizar
        phonemes = phonemize(text)
        phoneme_list = list(phonemes)
        phoneme_list.insert(0, self._BOS)

        # Convertir a IDs
        ids = self._phoneme_to_ids(phoneme_list)
        input_ids = np.expand_dims(np.array(ids, dtype=np.int64), 0)
        input_len = np.array([len(ids)], dtype=np.int64)

        # Parámetros de inferencia desde el config
        inf_cfg = self._config.get("inference", {})
        noise_scale = float(inf_cfg.get("noise_scale", 0.667))
        length_scale = float(inf_cfg.get("length_scale", 1.0))
        noise_w = float(inf_cfg.get("noise_w", 0.8))

        scales = np.array([noise_scale, length_scale, noise_w], dtype=np.float32)

        feed = {
            "input": input_ids,
            "input_lengths": input_len,
            "scales": scales,
        }
        if "sid" in self._sess_inputs:
            feed["sid"] = np.array([0], dtype=np.int64)

        # Inferencia ONNX
        samples = self._sess.run(None, feed)[0].squeeze()

        # Empaquetar como WAV
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(self.sample_rate)
            int_samples = (samples * 32767).astype(np.int16)
            wav.writeframes(int_samples.tobytes())

        audio = buf.getvalue()
        duration = len(audio) / (self.sample_rate * 2)
        logger.info("TTS: %d chars -> %d bytes WAV (%.1f s)", len(text), len(audio), duration)
        return audio
