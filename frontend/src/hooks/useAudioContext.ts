import { useRef, useEffect, useCallback } from "react";

/**
 * Hook que gestiona un único AudioContext global para toda la aplicación.
 * Evita la creación múltiple de AudioContexts que causa problemas de autoplay
 * y políticas del navegador/WebView2.
 */
export function useAudioContext() {
  const audioCtxRef = useRef<AudioContext | null>(null);

  const getOrCreate = useCallback((): AudioContext => {
    if (!audioCtxRef.current || audioCtxRef.current.state === "closed") {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      audioCtxRef.current = new AudioCtx();
    }
    return audioCtxRef.current;
  }, []);

  const ensureResumed = useCallback(async (): Promise<AudioContext> => {
    const ctx = getOrCreate();
    if (ctx.state === "suspended") {
      try {
        await ctx.resume();
      } catch (e) {
        console.warn("[useAudioContext] resume() falló:", e);
      }
    }
    return ctx;
  }, [getOrCreate]);

  const playBeep = useCallback(
    (isStart: boolean) => {
      try {
        const ctx = getOrCreate();
        if (ctx.state === "suspended") {
          ctx.resume().catch(() => {});
        }

        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        if (isStart) {
          // Tono de apertura de canal rápido (Box-In)
          osc.type = "sine";
          osc.frequency.setValueAtTime(650, ctx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.08);
          gain.gain.setValueAtTime(0.08, ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.12);
          osc.start();
          osc.stop(ctx.currentTime + 0.12);
        } else {
          // Tono de cierre de canal descendente (Box-Out)
          osc.type = "triangle";
          osc.frequency.setValueAtTime(750, ctx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(450, ctx.currentTime + 0.15);
          gain.gain.setValueAtTime(0.04, ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.18);
          osc.start();
          osc.stop(ctx.currentTime + 0.18);
        }
      } catch (e) {
        console.warn("[useAudioContext] No se pudo reproducir click de radio:", e);
      }
    },
    [getOrCreate]
  );

  // Cerrar el contexto al desmontar
  useEffect(() => {
    return () => {
      if (audioCtxRef.current && audioCtxRef.current.state !== "closed") {
        audioCtxRef.current.close().catch(() => {});
        audioCtxRef.current = null;
      }
    };
  }, []);

  return {
    audioCtx: audioCtxRef, // expuesto como ref para pasar a useAudioCapture
    getOrCreate,
    ensureResumed,
    playBeep,
  };
}

export default useAudioContext;
