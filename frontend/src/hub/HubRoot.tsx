import { useEffect, useRef, useState } from "react";
import { AppShell } from "./AppShell";
import { useAppStore } from "../store/config";
import useWebSocket from "../hooks/useWebSocket";
import useHotkey from "../hooks/useHotkey";
import useAudioCapture from "../hooks/useAudioCapture";
import useAudioContext from "../hooks/useAudioContext";
import { getHealth } from "../services/api";
import { audioQueue } from "../services/audioQueue";
import { registerAudioUnlock } from "../services/audioUnlock";
import { fetchUpdateNotice, openReleaseUrl } from "../services/updateChecker";
import { isDesktopUpdaterAvailable } from "../services/desktopUpdate";
import { useSessionHistoryPersistence } from "../core/history/useSessionHistoryPersistence";
import { useOverlayStatePublish } from "../core/sync/useOverlayStatePublish";
import { useOverlayVisibility } from "./hooks/useOverlayVisibility";
import { getPlatform } from "../core/platform";
import {
  buildPttQuestionText,
  resolvePttQuestion,
} from "./pttPipeline";

const isSpeechRecognitionAvailable =
  typeof window !== "undefined" &&
  ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

export function HubRoot() {
  const {
    setBackendHealth,
    setRadioMode,
    setCurrentTokens,
    setVoicePlaybackText,
    setLatestAdvice,
    addMessageToHistory,
    updateConfig,
    connectivity,
  } = useAppStore();

  const [updateNotice, setUpdateNotice] = useState<{
    latest_version: string;
    release_url: string;
    release_name?: string;
  } | null>(null);

  const { sendJson, clearPendingTts } = useWebSocket();
  const { audioCtx, ensureResumed, playBeep } = useAudioContext();
  const { startCapture, stopCapture } = useAudioCapture(audioCtx);

  useSessionHistoryPersistence();
  useOverlayStatePublish();
  useOverlayVisibility();

  useEffect(() => {
    const { config } = useAppStore.getState();
    const platform = getPlatform();
    if (platform.updatePttHotkeys) {
      void platform.updatePttHotkeys({
        start: config.pttHotkey,
        stop: config.pttStopHotkey,
      });
    }
  }, []);

  useEffect(() => {
    registerAudioUnlock(async () => {
      await ensureResumed();
    });
    audioQueue.setOnPlaybackChange((isPlaying, text) => {
      if (isPlaying) {
        setVoicePlaybackText(text?.trim() || useAppStore.getState().radio.latestAdvice);
        setRadioMode("SPEAKING_ENGINE");
      } else {
        setVoicePlaybackText("");
        setRadioMode("IDLE");
      }
    });
  }, [setRadioMode, setVoicePlaybackText, ensureResumed]);

  const recognitionRef = useRef<any>(null);
  const transcriptionRef = useRef<string>("");
  const isRecognizingRef = useRef(false);

  const startSpeechRecognition = () => {
    if (isRecognizingRef.current) return;
    try {
      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (!SpeechRecognition) return;

      isRecognizingRef.current = true;
      const rec = new SpeechRecognition();
      rec.lang = "es-ES";
      rec.continuous = true;
      rec.interimResults = true;
      rec.maxAlternatives = 1;
      rec.onresult = (e: any) => {
        let combined = "";
        for (let i = 0; i < e.results.length; i++) {
          combined += e.results[i][0]?.transcript ?? "";
        }
        transcriptionRef.current = combined;
      };
      rec.onerror = () => {
        isRecognizingRef.current = false;
        recognitionRef.current = null;
      };
      rec.onend = () => {
        isRecognizingRef.current = false;
        recognitionRef.current = null;
      };
      transcriptionRef.current = "";
      recognitionRef.current = rec;
      rec.start();
    } catch {
      isRecognizingRef.current = false;
    }
  };

  const stopSpeechRecognition = (): Promise<void> =>
    new Promise((resolve) => {
      const rec = recognitionRef.current;
      if (!rec || !isRecognizingRef.current) {
        resolve();
        return;
      }
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        isRecognizingRef.current = false;
        recognitionRef.current = null;
        resolve();
      };
      rec.onend = finish;
      rec.onerror = finish;
      try {
        rec.stop();
      } catch {
        finish();
      }
      window.setTimeout(finish, 1500);
    });

  const handlePTTStart = () => {
    const state = useAppStore.getState();
    if (state.radio.mode === "LISTENING_PILOT") return;
    audioQueue.stop();
    clearPendingTts();
    sendJson("pilot_ptt_barge_in", {});
    setRadioMode("LISTENING_PILOT");
    setCurrentTokens("");
    void ensureResumed();
    playBeep(true);
    startCapture();
    startSpeechRecognition();
  };

  const handlePTTEnd = async () => {
    const state = useAppStore.getState();
    if (state.radio.mode !== "LISTENING_PILOT") return;
    setRadioMode("THINKING_LLM");
    playBeep(false);
    const wavBlob = stopCapture();
    await stopSpeechRecognition();
    await new Promise((resolve) => setTimeout(resolve, 100));

    const config = useAppStore.getState().config;
    const baseUrl = `http://${config.vllmIP}:${config.serverPort}`;
    const questionText = await buildPttQuestionText(
      transcriptionRef.current,
      wavBlob,
      baseUrl,
    );

    const resolved = resolvePttQuestion(questionText);
    if (resolved.status === "empty") {
      setLatestAdvice(resolved.message);
      setRadioMode("IDLE");
      setCurrentTokens("");
      return;
    }

    addMessageToHistory("pilot", resolved.question);
    console.log("[PTT] Enviando pregunta:", resolved.question);
    sendJson("pilot_question", { question: resolved.question });
  };

  const handlePTTStartRef = useRef(handlePTTStart);
  const handlePTTEndRef = useRef(handlePTTEnd);
  handlePTTStartRef.current = handlePTTStart;
  handlePTTEndRef.current = handlePTTEnd;

  useHotkey({
    onKeyDown: () => handlePTTStartRef.current(),
    onKeyUp: () => handlePTTEndRef.current(),
  });

  useEffect(() => {
    if (!getPlatform().isElectron) return;
    const bridge = window.vantare;
    if (!bridge?.subscribePtt) return;
    return bridge.subscribePtt((action) => {
      if (action === "down") handlePTTStartRef.current();
      else if (action === "up") handlePTTEndRef.current();
      else {
        const mode = useAppStore.getState().radio.mode;
        if (mode === "LISTENING_PILOT") handlePTTEndRef.current();
        else handlePTTStartRef.current();
      }
    });
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || (window as any).__TAURI_INTERNALS__ === undefined) return;
    let unlistenPromise: Promise<(() => void) | undefined> | null = null;
    unlistenPromise = import("@tauri-apps/api/event").then(async ({ listen }) =>
      listen("config-updated", (event: any) => updateConfig(event.payload)),
    );
    return () => {
      void unlistenPromise?.then((unlisten) => unlisten?.());
    };
  }, [updateConfig]);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const health = await getHealth();
        setBackendHealth({
          shared_memory:
            health.shared_memory.status === "connected" || health.shared_memory.status === "simulated",
          lmu_api:
            health.lmu_api.status === "online" ||
            health.lmu_api.status === "active" ||
            health.lmu_api.status === "ok",
          llm: health.llm.configured,
          websocket: useAppStore.getState().connectivity.wsStatus === "CONNECTED",
        });
      } catch {
        setBackendHealth(null);
      }
    };
    const bootDelay = setTimeout(checkHealth, 2000);
    const interval = setInterval(checkHealth, 15000);
    return () => {
      clearTimeout(bootDelay);
      clearInterval(interval);
    };
  }, [setBackendHealth]);

  useEffect(() => {
    if (isDesktopUpdaterAvailable()) {
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      const notice = await fetchUpdateNotice();
      if (!cancelled && notice?.update_available && notice.release_url) {
        setUpdateNotice({
          latest_version: notice.latest_version,
          release_url: notice.release_url,
          release_name: notice.release_name,
        });
      }
    }, 8000);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  const isBackendOnline =
    connectivity.wsStatus === "CONNECTED" || connectivity.backendHealth !== null;
  const isLmuOnline = !!(
    connectivity.backendHealth?.shared_memory || connectivity.backendHealth?.lmu_api
  );
  const isLlmOnline = !!connectivity.backendHealth?.llm;

  return (
    <>
      {updateNotice && (
        <div className="fixed top-0 inset-x-0 z-50 flex items-center justify-between px-4 py-2 bg-[#2a1018] border-b border-a1-accent/30 text-xs">
          <span>Nueva versión disponible: v{updateNotice.latest_version}</span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => openReleaseUrl(updateNotice.release_url)}
              className="text-a1-accent hover:text-white uppercase font-bold"
            >
              Descargar
            </button>
            <button type="button" onClick={() => setUpdateNotice(null)} className="text-a1-text-muted">
              ✕
            </button>
          </div>
        </div>
      )}
      <AppShell backendOk={isBackendOnline} lmuOk={isLmuOnline} llmOk={isLlmOnline} />
      {!isSpeechRecognitionAvailable && (
        <div className="fixed bottom-3 right-3 text-[10px] text-a1-text-muted bg-hub-card border border-hub-border px-2 py-1 rounded">
          SpeechRecognition no disponible — usa texto o WAV fallback
        </div>
      )}
    </>
  );
}

export default HubRoot;
