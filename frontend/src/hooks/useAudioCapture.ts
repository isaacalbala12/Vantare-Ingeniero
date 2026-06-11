import { useState, useEffect, useRef, useCallback } from "react";
import { useAppStore } from "../store/config";

/**
 * Hook para gestionar la captura del micrófono por Web Audio API,
 * detección de palabra de activación por nivel RMS y generación de WAV Blob.
 * @param audioCtxRef Opcional — Ref a un AudioContext externo (desde useAudioContext).
 *                    Si no se provee, crea uno propio.
 */
export function useAudioCapture(audioCtxRef?: React.MutableRefObject<AudioContext | null>) {
  const { config, radio, setRadioMode } = useAppStore();
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [inputLevel, setInputLevel] = useState<number>(0);

  const internalCtxRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);
  const audioBuffersRef = useRef<Float32Array[]>([]);
  const sampleRateRef = useRef<number>(44100);

  const configRef = useRef(config);
  useEffect(() => {
    configRef.current = config;
  }, [config]);

  const radioModeRef = useRef(radio.mode);
  useEffect(() => {
    radioModeRef.current = radio.mode;
  }, [radio.mode]);

  // Conversión PCM de coma flotante a WAV 16-bit mono
  const bufferToWav = (buffers: Float32Array[], sampleRate: number): Blob => {
    let totalLength = 0;
    for (const b of buffers) {
      totalLength += b.length;
    }
    const result = new Float32Array(totalLength);
    let offset = 0;
    for (const b of buffers) {
      result.set(b, offset);
      offset += b.length;
    }

    const buffer = new ArrayBuffer(44 + result.length * 2);
    const view = new DataView(buffer);

    // Escribir cabecera RIFF/WAVE
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + result.length * 2, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM lineal
    view.setUint16(22, 1, true); // Canal Mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // Byte rate
    view.setUint16(32, 2, true); // Block align
    view.setUint16(34, 16, true); // 16 bits por muestra
    writeString(view, 36, 'data');
    view.setUint32(40, result.length * 2, true);

    // Escribir muestras PCM
    let index = 44;
    for (let i = 0; i < result.length; i++) {
      let sample = result[i];
      sample = Math.max(-1, Math.min(1, sample));
      view.setInt16(index, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true);
      index += 2;
    }

    return new Blob([view], { type: 'audio/wav' });
  };

  const writeString = (view: DataView, offset: number, string: string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  };

  const isRecordingRef = useRef(false);

  const startCapture = async () => {
    if (isRecordingRef.current) return;
    
    audioBuffersRef.current = [];
    isRecordingRef.current = true;
    setIsRecording(true);

    try {
      const constraints: MediaStreamConstraints = {
        audio: configRef.current.micDevice && configRef.current.micDevice !== "default"
          ? { deviceId: { exact: configRef.current.micDevice } }
          : true,
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      mediaStreamRef.current = stream;

      // Usar AudioContext externo (desde useAudioContext) o crear uno interno
      let audioCtx: AudioContext;
      if (audioCtxRef?.current && audioCtxRef.current.state !== "closed") {
        audioCtx = audioCtxRef.current;
        if (audioCtx.state === "suspended") {
          audioCtx.resume().catch(() => {});
        }
      } else {
        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
        audioCtx = new AudioCtx();
      }
      internalCtxRef.current = audioCtx;
      sampleRateRef.current = audioCtx.sampleRate;

      const source = audioCtx.createMediaStreamSource(stream);
      // ScriptProcessorNode para compatibilidad multiplataforma simplificada
      const processor = audioCtx.createScriptProcessor(2048, 1, 1);
      processorNodeRef.current = processor;

      source.connect(processor);
      processor.connect(audioCtx.destination);

      processor.onaudioprocess = (e) => {
        const inputBuffer = e.inputBuffer.getChannelData(0);
        
        // Almacenar muestras
        const bufferCopy = new Float32Array(inputBuffer.length);
        bufferCopy.set(inputBuffer);
        audioBuffersRef.current.push(bufferCopy);

        // Calcular RMS (nivel de amplitud)
        let sumSquares = 0;
        for (let i = 0; i < inputBuffer.length; i++) {
          sumSquares += inputBuffer[i] * inputBuffer[i];
        }
        const rms = Math.sqrt(sumSquares / inputBuffer.length);
        
        // Escalar RMS (0-100) para el vúmetro
        const level = Math.min(100, Math.round(rms * 300));
        setInputLevel(level);

        // Detección de Wake Word por amplitud — solo si está habilitado explícitamente
        if (radioModeRef.current === "IDLE" && configRef.current.wakeWordEnabled) {
          const threshold = Math.max(0.02, (105 - configRef.current.sensitivity) / 400);
          if (rms > threshold) {
            console.log(`[useAudioCapture] Wake word (RMS): ${rms.toFixed(4)} > ${threshold.toFixed(4)}`);
            setRadioMode("LISTENING_PILOT");
          }
        }
      };
    } catch (err) {
      console.error("[useAudioCapture] Error inicializando micrófono:", err);
      isRecordingRef.current = false;
      setIsRecording(false);
    }
  };

  const stopCapture = useCallback(() => {
    if (!isRecordingRef.current) return null;
    
    isRecordingRef.current = false;
    setIsRecording(false);
    setInputLevel(0);

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (processorNodeRef.current) {
      processorNodeRef.current.disconnect();
      processorNodeRef.current = null;
    }

    // Solo cerrar el contexto si fue creado internamente (no compartido)
    if (internalCtxRef.current && !audioCtxRef?.current) {
      if (internalCtxRef.current.state !== "closed") {
        internalCtxRef.current.close();
      }
      internalCtxRef.current = null;
    } else {
      internalCtxRef.current = null;
    }

    if (audioBuffersRef.current.length > 0) {
      const wavBlob = bufferToWav(audioBuffersRef.current, sampleRateRef.current);
      return wavBlob;
    }

    return null;
  }, [audioCtxRef]);

  useEffect(() => {
    return () => {
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      }
      // Solo cerrar contexto interno (no compartido)
      if (internalCtxRef.current && !audioCtxRef?.current) {
        if (internalCtxRef.current.state !== "closed") {
          internalCtxRef.current.close();
        }
      }
      internalCtxRef.current = null;
    };
  }, [audioCtxRef]);

  return {
    isRecording,
    inputLevel,
    startCapture,
    stopCapture,
  };
}

export default useAudioCapture;

