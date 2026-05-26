import { useCallback, useRef } from "react";
import { useAppStore } from "../store/config";
import { useAudioCapture } from "./useAudioCapture";
import { useAudioContext } from "./useAudioContext";
import { useWebSocket } from "./useWebSocket";

/**
 * Hook para iniciar/detener la captura de audio PTT (Push-To-Talk).
 * Encapsula la lógica de handlePTTStart y handlePTTEnd para que pueda
 * ser usado tanto por el hotkey como por el botón de emergencia.
 * 
 * Este hook NO registra listeners de teclado - eso lo hace useHotkey.
 * Este hook solo proporciona las funciones de inicio/fin PTT.
 */
export function usePTT() {
  const { audioCtx, ensureResumed } = useAudioContext();
  const { startCapture, stopCapture } = useAudioCapture(audioCtx);
  const { sendBinary, sendJson } = useWebSocket();

  const pilotWsRef = useRef<WebSocket | null>(null);
  const processingRef = useRef(false);

  const setRadioMode = useAppStore((s) => s.setRadioMode);
  const setMicLevel = useAppStore((s) => s.setMicLevel);
  const addMessageToHistory = useAppStore((s) => s.addMessageToHistory);
  const setLatestAdvice = useAppStore((s) => s.setLatestAdvice);
  const setCurrentTokens = useAppStore((s) => s.setCurrentTokens);
  const wsStatus = useAppStore((s) => s.connectivity.wsStatus);
  const config = useAppStore((s) => s.config);

  /**
   * Inicia la captura de audio PTT
   */
  const pttStart = useCallback(async () => {
    const state = useAppStore.getState();
    if (state.radio.mode !== "IDLE") {
      console.log("[PTT] Ignorado: modo no es IDLE");
      return;
    }

    setRadioMode("LISTENING_PILOT");
    console.log("[PTT] Iniciado — Abriendo micrófono...");

    await ensureResumed();
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        deviceId: config.micDevice !== "default" ? { exact: config.micDevice } : undefined,
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    const audioTrack = stream.getAudioTracks()[0];
    const audioContext = new AudioContext({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);

    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    const updateLevel = () => {
      if (useAppStore.getState().radio.mode !== "LISTENING_PILOT") return;
      analyser.getByteFrequencyData(dataArray);
      const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
      setMicLevel(avg / 255);
      requestAnimationFrame(updateLevel);
    };
    updateLevel();

    const chunks: Uint8Array[] = [];
    const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(new Uint8Array(await e.data.arrayBuffer()));
    };

    const sendAudio = () => {
      if (chunks.length === 0) return;
      const combined = new Uint8Array(chunks.reduce((a, b) => a + b.length, 0));
      let offset = 0;
      for (const chunk of chunks) {
        combined.set(chunk, offset);
        offset += chunk.length;
      }
      sendBinary(combined);
      chunks.length = 0;
    };

    mediaRecorder.start(100);
    (window as any).__PTT_MEDIA_RECORDER__ = mediaRecorder;
    (window as any).__PTT_AUDIO_CONTEXT__ = audioContext;
    (window as any).__PTT_STREAM__ = stream;
    (window as any).__PTT_SEND_AUDIO__ = sendAudio;

    startCapture(stream);
  }, [audioCtx, ensureResumed, startCapture, setRadioMode, setMicLevel, sendBinary, config.micDevice]);

  /**
   * Detiene la captura de audio PTT y envía el audio al backend
   */
  const pttEnd = useCallback(async () => {
    const state = useAppStore.getState();
    if (state.radio.mode !== "LISTENING_PILOT") return;

    console.log("[PTT] Finalizado — Procesando audio...");
    setMicLevel(0);

    const mediaRecorder = (window as any).__PTT_MEDIA_RECORDER__ as MediaRecorder | undefined;
    const audioContext = (window as any).__PTT_AUDIO_CONTEXT__ as AudioContext | undefined;
    const stream = (window as any).__PTT_STREAM__ as MediaStream | undefined;
    const sendAudio = (window as any).__PTT_SEND_AUDIO__ as (() => void) | undefined;

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }

    await new Promise((resolve) => setTimeout(resolve, 200));

    if (sendAudio) sendAudio();

    setRadioMode("THINKING_LLM");

    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
    }
    if (audioContext) {
      audioContext.close().catch(() => {});
    }

    delete (window as any).__PTT_MEDIA_RECORDER__;
    delete (window as any).__PTT_AUDIO_CONTEXT__;
    delete (window as any).__PTT_STREAM__;
    delete (window as any).__PTT_SEND_AUDIO__;

    stopCapture();
  }, [setRadioMode, setMicLevel, stopCapture]);

  return {
    pttStart,
    pttEnd,
  };
}

export default usePTT;
