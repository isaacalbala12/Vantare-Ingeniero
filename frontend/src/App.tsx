import React, { useEffect, useRef } from "react";
import Dashboard from "./components/RadioOverlay";
import ConfigTab from "./components/ConfigTab";
import { useAppStore } from "./store/config";
import useWebSocket from "./hooks/useWebSocket";
import useHotkey from "./hooks/useHotkey";
import useAudioCapture from "./hooks/useAudioCapture";
import useAudioContext from "./hooks/useAudioContext";
import { getHealth } from "./services/api";
import { audioQueue } from "./services/audioQueue";
import { getCurrentWindow } from "@tauri-apps/api/window";

// Verificar disponibilidad de Web Speech API
const isSpeechRecognitionAvailable = 
  typeof window !== "undefined" && 
  ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);

/**
 * Hub Unificado - Una sola ventana Tauri con Dashboard y Configuración.
 * Integra WebSocket, captura de audio PTT, hotkeys, síntesis de beeps,
 * y alterna entre Dashboard y Configuración según el estado screen.
 */
export const App: React.FC = () => {
  const {
    setBackendHealth,
    setRadioMode,
    setCurrentTokens,
    addMessageToHistory,
    updateConfig,
    connectivity,
    screen,
    setScreen,
  } = useAppStore();

  // 1. Inicializar WebSocket (se conecta automáticamente en useEffect interno)
  const { sendJson } = useWebSocket();

  // 2. Inicializar AudioContext global (compartido entre beeps y captura)
  const { audioCtx, ensureResumed, playBeep } = useAudioContext();

  // 3. Inicializar Captura de Audio con el AudioContext compartido
  const { startCapture, stopCapture } = useAudioCapture(audioCtx);

  // Vincular cola TTS con el estado de radio
  useEffect(() => {
    audioQueue.setOnPlaybackChange((isPlaying) => {
      if (isPlaying) {
        setRadioMode("SPEAKING_ENGINE");
      } else {
        setRadioMode("IDLE");
      }
    });
  }, [setRadioMode]);

  // 3a. Pre-calentar permiso de micrófono al montar la app para evitar que
  //     WebView2 bloquee el message loop con el diálogo modal de permiso.
  useEffect(() => {
    const prewarmMic = setTimeout(async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((t) => t.stop());
        console.log("[App] Permiso de micrófono pre-calentado");
      } catch (e) {
        // No crítico: si falla aquí, el permiso se pedirá cuando el usuario pulse PTT
        console.warn("[App] Pre-warm de micrófono:", e);
      }
    }, 2000);
    return () => clearTimeout(prewarmMic);
  }, []);

  // Referencias para el control asíncrono de la transcripción
  const recognitionRef = useRef<any>(null);
  const transcriptionRef = useRef<string>("");
  const isRecognizingRef = useRef(false);



  // 3. Beeps táctiles gestionados por useAudioContext (comparten el mismo AudioContext global)

  // 5. Inicializar y gestionar la API de reconocimiento de voz del navegador
  const startSpeechRecognition = () => {
    if (isRecognizingRef.current) return;
    try {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (!SpeechRecognition) {
        console.warn("[App] Web Speech Recognition no está soportado en este navegador.");
        return;
      }

      isRecognizingRef.current = true;
      const rec = new SpeechRecognition();
      rec.lang = "es-ES";
      rec.continuous = false;
      rec.interimResults = false;
      rec.maxAlternatives = 1;

      rec.onresult = (e: any) => {
        const result = e.results[0][0].transcript;
        console.log("[App] Transcripción capturada:", result);
        transcriptionRef.current = result;
      };

      rec.onerror = (e: any) => {
        isRecognizingRef.current = false;
        recognitionRef.current = null;
        const errorType = e.error || "unknown";
        switch (errorType) {
          case "no-speech":
          case "aborted":
            // Errores esperados — no hacer nada
            break;
          case "audio-capture":
          case "not-allowed":
            console.warn(`[App] SpeechRecognition: ${errorType} — micrófono no disponible.`);
            break;
          case "network":
          case "service-not-allowed":
            console.warn(`[App] SpeechRecognition: ${errorType} — reintentando en 1s...`);
            setTimeout(() => {
              if (!isRecognizingRef.current) startSpeechRecognition();
            }, 1000);
            break;
          default:
            console.error(`[App] SpeechRecognition error: ${errorType}`, e);
        }
      };

      rec.onend = () => {
        isRecognizingRef.current = false;
        recognitionRef.current = null;
        console.log("[App] Reconocimiento de voz finalizado.");
      };

      transcriptionRef.current = "";
      recognitionRef.current = rec;
      rec.start();
    } catch (e) {
      console.error("[App] Fallo al instanciar SpeechRecognition:", e);
      isRecognizingRef.current = false;
    }
  };

  const stopSpeechRecognition = () => {
    try {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
        recognitionRef.current = null;
      }
    } catch (e) {
      console.error("[App] Error al apagar SpeechRecognition:", e);
      recognitionRef.current = null;
    }
    isRecognizingRef.current = false;
  };

  // 6. Orquestadores Push-To-Talk (PTT)
  const handlePTTStart = () => {
    const state = useAppStore.getState();
    if (state.radio.mode === "LISTENING_PILOT") return;

    // Interrumpir reproducción de audio TTS en curso
    audioQueue.stop();

    console.log("[App] PTT Iniciado — Abriendo micrófono...");
    setRadioMode("LISTENING_PILOT");
    setCurrentTokens("");

    // Asegurar que el AudioContext esté resumed (política de autoplay)
    ensureResumed();

    // Sonido de apertura
    playBeep(true);

    // Iniciar grabación de audio y dictado por voz
    startCapture();
    startSpeechRecognition();
  };

  const handlePTTEnd = async () => {
    const state = useAppStore.getState();
    if (state.radio.mode !== "LISTENING_PILOT") return;

    console.log("[App] PTT Finalizado — Procesando audio...");
    setRadioMode("THINKING_LLM");

    // Sonido de cierre de mic
    playBeep(false);

    // Detener grabación de audio física
    const wavBlob = stopCapture();

    // Detener reconocimiento de voz
    stopSpeechRecognition();

    // Dar 200ms para que se asiente la transcripción final del Speech API
    await new Promise((resolve) => setTimeout(resolve, 200));

    // Determinar pregunta final (solo si hay transcripción válida)
    let questionText = transcriptionRef.current.trim();
    
    // Fallback WAV: if SpeechRecognition didn't capture text, send audio to backend for ASR
    if (!questionText && wavBlob && wavBlob.size > 0) {
      console.log("[App] SpeechRecognition sin transcripción — enviando WAV para ASR");
      try {
        const config = useAppStore.getState().config;
        const baseUrl = `http://${config.vllmIP}:${config.serverPort}`;
        const formData = new FormData();
        formData.append("audio", wavBlob, "ptt_recording.wav");
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);
        
        const res = await fetch(`${baseUrl}/transcribe`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        
        if (res.ok) {
          const data = await res.json();
          questionText = (data.text || "").trim();
        }
      } catch (err) {
        console.warn("[App] Fallback ASR falló:", err);
      }
    }

    if (!questionText) {
      console.warn("[App] No se capturó transcripción de voz.");
      setRadioMode("IDLE");
      setCurrentTokens("");
      return;
    }

    // Añadir mensaje del piloto al historial del chat
    addMessageToHistory("pilot", questionText);

    // Enviar evento de texto por websocket
    sendJson("pilot_question", { question: questionText });


    // La respuesta del LLM llega via WebSocket (advice_token/advice_end).
    // El backend procesa pilot_question a traves del IntelligenceEngine
    // y el TTS se solicita al endpoint /tts cuando llega advice_end.
  };

  // Handler para envío de texto directo (fallback cuando SpeechRecognition no disponible en Linux)
  const handleTextSubmit = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    console.log("[App] Texto enviado:", trimmed);
    
    // Interrumpir reproducción de audio TTS en curso
    audioQueue.stop();
    
    // Añadir mensaje del piloto al historial
    addMessageToHistory("pilot", trimmed);
    
    // Cambiar modo a pensando
    setRadioMode("THINKING_LLM");
    setCurrentTokens("");

    try {
      const config = useAppStore.getState().config;
      const baseUrl = `http://${config.vllmIP}:${config.serverPort}`;
      
      // Paso 1: POST /ask → obtener texto de la respuesta del LLM
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);

      let response: Response;
      try {
        response = await fetch(`${baseUrl}/ask`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: trimmed }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
      } catch (err: any) {
        if (err.name === "AbortError") {
          console.warn("[App] Timeout en /ask (15s)");
          setRadioMode("IDLE");
          return;
        }
        throw err;
      } finally {
        clearTimeout(timeoutId);
      }

      // Leer la respuesta como texto (Content-Type: text/plain)
      const responseText = await response.text();
      
      if (!responseText || responseText.trim() === "") {
        console.warn("[App] Respuesta vacía del LLM.");
        setRadioMode("IDLE");
        return;
      }

      // Añadir el texto al historial como mensaje del ingeniero
      addMessageToHistory("engineer", responseText);

      // Paso 2: GET /tts?text=... → obtener audio MP3/WAV
      try {
        const ttsResponse = await fetch(`${baseUrl}/tts?text=${encodeURIComponent(responseText)}`);
        
        if (ttsResponse.ok) {
          const audioBlob = await ttsResponse.blob();
          
          if (audioBlob.size > 0) {
            const url = URL.createObjectURL(audioBlob);
            audioQueue.enqueue(responseText, url);
            // El modo SPEAKING_ENGINE se activará automáticamente vía callback
          } else {
            console.warn("[App] Audio vacío recibido del TTS.");
            setRadioMode("IDLE");
          }
        } else {
          console.warn("[App] Error al obtener TTS:", ttsResponse.status);
          setRadioMode("IDLE");
        }
      } catch (ttsError) {
        console.warn("[App] Error en solicitud TTS:", ttsError);
        // Mostrar el texto en el historial sin audio
        setRadioMode("IDLE");
      }
    } catch (error) {
      console.error("[App] Error al enviar pregunta:", error);
      setRadioMode("IDLE");
      setCurrentTokens("");
    }
  };

  // 6. Registrar interceptación de Teclado (PTT local y global)
  useHotkey({
    onKeyDown: handlePTTStart,
    onKeyUp: handlePTTEnd,
  });

  // 8. Escuchar el evento Tauri global de guardado para sincronizar ventanas independientes
  useEffect(() => {
    let unlistenPromise: Promise<any> | null = null;

    if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined) {
      unlistenPromise = import("@tauri-apps/api/event").then(async ({ listen }) => {
        return await listen("config-updated", (event: any) => {
          console.log("[App] Sincronizando store con nueva configuración de Tauri:", event.payload);
          updateConfig(event.payload);
        });
      });
    }

    return () => {
      if (unlistenPromise) {
        unlistenPromise.then((unlisten) => {
          if (unlisten) unlisten();
        }).catch(e => console.error(e));
      }
    };
  }, [updateConfig]);



  // 9. Polling de salud periódica al backend REST API (cada 5s)
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const health = await getHealth();
        setBackendHealth({
          shared_memory: health.shared_memory.status === "connected" || health.shared_memory.status === "simulated",
          lmu_api: health.lmu_api.status === "online" || health.lmu_api.status === "active" || health.lmu_api.status === "ok",
          llm: health.llm.configured,
          websocket: useAppStore.getState().connectivity.wsStatus === "CONNECTED",
        });
      } catch (e) {
        console.warn("[App] Polling de salud fallido (servidor desconectado).");
        setBackendHealth(null);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => clearInterval(interval);
  }, [setBackendHealth]);



  const isBackendOnline = connectivity.wsStatus === "CONNECTED" || connectivity.backendHealth !== null;
  const isLmuOnline = !!(connectivity.backendHealth?.shared_memory || connectivity.backendHealth?.lmu_api);
  const isLlmOnline = !!connectivity.backendHealth?.llm;

  const handleMinimize = async () => {
    try {
      const win = getCurrentWindow();
      await win.minimize();
    } catch (e) { console.warn("[App] minimize:", e); }
  };
  const handleMaximize = async () => {
    try {
      const win = getCurrentWindow();
      const isMaximized = await win.isMaximized();
      if (isMaximized) {
        await win.unmaximize();
      } else {
        await win.maximize();
      }
    } catch (e) { console.warn("[App] maximize:", e); }
  };
  const handleClose = async () => {
    try {
      const win = getCurrentWindow();
      await win.close();
    } catch (e) { console.warn("[App] close:", e); }
  };

  return (
    <div className="w-screen h-screen overflow-hidden bg-[#111] text-white flex flex-col justify-between select-none" style={{ fontFamily: "system-ui, sans-serif" }}>
      {/* Barra superior de indicadores de estado + controles de ventana */}
      <div data-tauri-drag-region className="flex items-center justify-between px-3 py-2 bg-[#000] border-b border-[#222] text-xs font-mono font-bold h-[35px]">
        <div className="flex gap-4">
          <div className="flex items-center gap-1.5">
            <span className={isBackendOnline ? "text-green-500" : "text-red-500"}>●</span>
            <span>BACKEND</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className={isLmuOnline ? "text-green-500" : "text-red-500"}>●</span>
            <span>LMU</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className={isLlmOnline ? "text-green-500" : "text-red-500"}>●</span>
            <span>LLM</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-[#666] text-[10px] mr-3">Vantare AI Hub</div>
          <button onClick={handleMinimize} className="text-[#666] hover:text-white text-[14px] leading-none w-5 h-5 flex items-center justify-center rounded hover:bg-[#333]">─</button>
          <button onClick={handleMaximize} className="text-[#666] hover:text-white text-[14px] leading-none w-5 h-5 flex items-center justify-center rounded hover:bg-[#333]">□</button>
          <button onClick={handleClose} className="text-[#666] hover:text-red-500 text-[14px] leading-none w-5 h-5 flex items-center justify-center rounded hover:bg-[#333]">✕</button>
        </div>
      </div>

      {/* Contenido principal que alterna entre Dashboard y Configuración */}
      <div className="flex-1 overflow-hidden relative bg-[#111]">
        {screen === "config" ? <ConfigTab /> : <Dashboard onPTTStart={handlePTTStart} onPTTEnd={handlePTTEnd} onTextSubmit={handleTextSubmit} showTextInput={!isSpeechRecognitionAvailable} />}
      </div>

      {/* Barra inferior de navegación */}
      <div className="flex bg-[#000] border-t border-[#222] h-[45px] text-xs font-bold font-mono">
        <button
          onClick={() => setScreen("dashboard")}
          className={`flex-1 flex items-center justify-center transition-none uppercase ${
            screen === "dashboard" ? "bg-[#8a2be2] text-white" : "bg-[#111] text-[#aaa] hover:text-white"
          }`}
        >
          [Dashboard]
        </button>
        <button
          onClick={() => setScreen("config")}
          className={`flex-1 flex items-center justify-center transition-none uppercase ${
            screen === "config" ? "bg-[#8a2be2] text-white" : "bg-[#111] text-[#aaa] hover:text-white"
          }`}
        >
          [Configuración]
        </button>
      </div>
    </div>
  );
};

export default App;
