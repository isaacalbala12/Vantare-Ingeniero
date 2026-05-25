import { useEffect, useRef, useState, useCallback } from "react";
import { useAppStore } from "../store/config";
import { audioQueue } from "../services/audioQueue";

/**
 * Hook para la conexión y parseo de mensajes en tiempo real vía WebSocket.
 * Implementa la conexión real a ws://${vllmIP}:${serverPort}/ws con reconexión automática
 * y backoff exponencial, calculando latencia y mapeando mensajes al store global.
 */
export function useWebSocket() {
  const {
    config,
    setWsStatus,
    setLatency,
    updateTelemetry,
    setRadioMode,
    setCurrentTokens,
    addMessageToHistory,
    setLatestAdvice,
    setLatestAlert,
  } = useAppStore();

  const [lastTelemetry, setLastTelemetry] = useState<any>(null);
  const [lastAdvice, setLastAdvice] = useState<any>(null);
  const [lastAlert, setLastAlert] = useState<any>(null);
  const [lastPending, setLastPending] = useState<any>(null);
  const [lastStrategy, setLastStrategy] = useState<any>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectDelayRef = useRef<number>(1000); // Backoff inicial a 1s
  const manuallyClosedRef = useRef<boolean>(false);
  const ttsQueueRef = useRef<string[]>([]);
  const isTtsProcessingRef = useRef<boolean>(false);

  // Guardar referencias del store para evitar recrear funciones
  const currentTokensRef = useRef("");
  useEffect(() => {
    // Suscribirse a los tokens actuales en el store
    const unsub = useAppStore.subscribe((state) => {
      currentTokensRef.current = state.radio.currentTokens;
    });
    return unsub;
  }, []);

  // Función para procesar la cola de solicitudes TTS
  const processTtsQueue = useCallback(async () => {
    if (isTtsProcessingRef.current || ttsQueueRef.current.length === 0) return;

    isTtsProcessingRef.current = true;
    const fullText = ttsQueueRef.current.shift()!;

    const configState = useAppStore.getState().config;
    const baseUrl = `http://${configState.vllmIP || "localhost"}:${configState.serverPort || 8008}`;
    const ttsText = fullText.length > 2000 ? fullText.slice(0, 1997) + "..." : fullText;

    try {
      const res = await fetch(`${baseUrl}/tts?text=${encodeURIComponent(ttsText)}`);
      if (!res.ok) throw new Error(`TTS returned ${res.status}`);
      const audioBlob = await res.blob();
      if (!audioBlob || audioBlob.size === 0) throw new Error("TTS returned empty audio blob");

      const url = URL.createObjectURL(audioBlob);
      const currentMode = useAppStore.getState().radio.mode;
      if (currentMode !== "IDLE") {
        console.log("[WS] TTS listo pero usuario activo — descartando reproducción");
        URL.revokeObjectURL(url);
        isTtsProcessingRef.current = false;
        processTtsQueue();
        return;
      }
      setRadioMode("SPEAKING_ENGINE");
      audioQueue.enqueue(fullText, url);
    } catch (err) {
      console.warn("[WS] TTS no disponible:", err);
    } finally {
      isTtsProcessingRef.current = false;
      processTtsQueue();
    }
  }, [setRadioMode]);

  const connect = useCallback(() => {
    if (socketRef.current && (socketRef.current.readyState === WebSocket.CONNECTING || socketRef.current.readyState === WebSocket.OPEN)) {
      return;
    }

    manuallyClosedRef.current = false;
    setWsStatus("CONNECTING");

    // Construir la URL con el IP y puerto del store
    const vllmIP = config.vllmIP || "localhost";
    const serverPort = config.serverPort || 8008;
    const wsUrl = `ws://${vllmIP}:${serverPort}/ws`;

    console.log(`[useWebSocket] Conectando a ${wsUrl}...`);

    try {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        console.log("[useWebSocket] Conectado exitosamente.");
        setWsStatus("CONNECTED");
        reconnectDelayRef.current = 1000; // Resetear backoff
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
      };

      ws.onmessage = (event) => {
        let parsed: any;
        try {
          parsed = JSON.parse(event.data);
        } catch (e) {
          console.error("[useWebSocket] Error parseando JSON:", e);
          return;
        }

        const payload = parsed.data || parsed;
        const eventType = parsed.event || payload.event;

        // Calcular latencia utilizando la marca de tiempo si está disponible
        const timestamp = payload.timestamp ?? parsed.timestamp;
        if (typeof timestamp === "number") {
          const msgTime = timestamp > 1e11 ? timestamp : timestamp * 1000;
          const lat = Math.max(0, Date.now() - msgTime);
          setLatency(lat);
        }

        // Procesar según el tipo de evento
        switch (eventType) {
          case "telemetry": {
            setLastTelemetry(payload);
            const player = payload.player || {};
            const engine = payload.engine || {};
            const tyres = payload.tyres || {};

            // 1. Detección robusta de velocidad en km/h
            let speed = 0;
            if (typeof payload.speed === "number") {
              speed = payload.speed;
            } else if (typeof player.speed === "number") {
              speed = player.speed;
            } else if (typeof engine.rpm === "number" && engine.rpm > 500) {
              // Estimación como fallback en base a las RPM y marcha
              // Si está en boxes o marcha neutra con RPM de ralentí, velocidad = 0
              if (player.in_pits === true || (engine.gear <= 0 && engine.rpm < 3000)) {
                speed = 0;
              } else {
                const rpmVal = engine.rpm;
                const gearVal = typeof engine.gear === "number" ? engine.gear : 1;
                const gearFactor = gearVal <= 0 ? 1 : gearVal;
                speed = Math.round(rpmVal * 0.03 * gearFactor);
              }
            }

            // 2. Mapeo de desgaste de neumáticos (0.0 nuevo, 1.0 gastado)
            let fl = 100, fr = 100, rl = 100, rr = 100;
            if (Array.isArray(tyres.wear) && tyres.wear.length === 4) {
              fl = Math.round((1.0 - tyres.wear[0]) * 100);
              fr = Math.round((1.0 - tyres.wear[1]) * 100);
              rl = Math.round((1.0 - tyres.wear[2]) * 100);
              rr = Math.round((1.0 - tyres.wear[3]) * 100);
            } else if (tyres.wear && typeof tyres.wear === "object") {
              fl = Math.round((1.0 - (tyres.wear.fl ?? 0)) * 100);
              fr = Math.round((1.0 - (tyres.wear.fr ?? 0)) * 100);
              rl = Math.round((1.0 - (tyres.wear.rl ?? 0)) * 100);
              rr = Math.round((1.0 - (tyres.wear.rr ?? 0)) * 100);
            }

            updateTelemetry({
              speed: Math.round(speed),
              rpm: Math.round(engine.rpm ?? 0),
              gear: engine.gear ?? 0,
              fuel: Number((player.fuel ?? payload.fuel ?? 0).toFixed(1)),
              lap: player.current_lap ?? player.lap ?? 1,
              position: player.place ?? player.position ?? 1,
              gaps: payload.gaps ?? { ahead: 0.0, behind: 0.0 },
              tyreWear: { fl, fr, rl, rr },
              alerts: payload.alerts ?? [],
            });
            break;
          }

          case "strategy": {
            setLastStrategy(payload);
            // El payload tiene fuel: { estimated_laps_remaining, fuel_needed_to_finish }
            // e información de neumáticos si se calculó en el optimizador
            if (payload.fuel) {
              updateTelemetry({
                fuel: Number(payload.fuel.fuel_in_tank ?? 0),
              });
            }
            if (payload.advice) {
              setLatestAdvice(payload.advice);
            }
            break;
          }

          case "llm_pending": {
            setLastPending(payload);
            setRadioMode("THINKING_LLM");
            break;
          }

          case "advice_start": {
            setLastAdvice(payload);
            setRadioMode("SPEAKING_ENGINE");
            setCurrentTokens("");
            break;
          }

          case "advice_token": {
            // El backend envía tokens de streaming individuales
            setRadioMode("SPEAKING_ENGINE");
            const token = payload.token || "";
            // El estado de tokens se actualiza acumulativamente
            setCurrentTokens(currentTokensRef.current + token);
            break;
          }

          case "advice_end": {
            setRadioMode("IDLE");
            const fullText = payload.full_text || "";
            if (fullText && !fullText.startsWith("---")) {
                setLatestAdvice(fullText);
            }
            if (fullText && !fullText.startsWith("---")) {
                addMessageToHistory("engineer", fullText);
            }
            setCurrentTokens("");

            // Añadir a la cola TTS para procesar secuencialmente
            if (fullText && !fullText.startsWith("---")) {
              ttsQueueRef.current.push(fullText);
              processTtsQueue();
            }
            break;
          }

          case "alert": {
            setLastAlert(payload);
            const alertMsg = payload.message || "";
            setLatestAlert(alertMsg);
            
            // Añadir a las alertas visuales del Spotter
            updateTelemetry({
              alerts: [alertMsg]
            });
            break;
          }

          default:
            console.log("[useWebSocket] Evento desconocido:", eventType, payload);
        }
      };

      ws.onclose = (event) => {
        console.warn(`[useWebSocket] Conexión cerrada. Código: ${event.code}.`);
        setWsStatus("DISCONNECTED");
        socketRef.current = null;

        // Intentar reconectar si no fue cerrado manualmente
        if (!manuallyClosedRef.current) {
          scheduleReconnect();
        }
      };

      ws.onerror = (err) => {
        console.error("[useWebSocket] Error de conexión:", err);
        setWsStatus("DISCONNECTED");
        ws.close();
      };
    } catch (err) {
      console.error("[useWebSocket] Excepción al conectar:", err);
      setWsStatus("DISCONNECTED");
      scheduleReconnect();
    }
  }, [
    config.vllmIP,
    config.serverPort,
    setWsStatus,
    setLatency,
    updateTelemetry,
    setRadioMode,
    setCurrentTokens,
    addMessageToHistory,
    setLatestAdvice,
    setLatestAlert,
    processTtsQueue,
  ]);

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      return;
    }

    console.log(`[useWebSocket] Programando reconexión en ${reconnectDelayRef.current}ms...`);
    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectTimeoutRef.current = null;
      // Incrementar el retardo exponencialmente hasta un máximo de 30s
      reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 30000);
      connect();
    }, reconnectDelayRef.current) as any;
  }, [connect]);

  const disconnect = useCallback(() => {
    manuallyClosedRef.current = true;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    setWsStatus("DISCONNECTED");
    console.log("[useWebSocket] Desconectado manualmente.");
  }, [setWsStatus]);

  // Manejar conexión automática al montar
  useEffect(() => {
    connect();
    return () => {
      // No desconectar al desmontar si queremos mantener la persistencia durante hot-reload en dev
      // pero sí limpiar temporizadores de reconexión.
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [connect]);

  // Permitir el envío de mensajes binarios (audio PCM/WAV)
  const sendBinary = useCallback((data: Blob | ArrayBuffer) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(data);
      return true;
    }
    console.warn("[useWebSocket] No se puede enviar datos, socket cerrado.");
    return false;
  }, []);

  // Permitir el envío de mensajes de texto en formato JSON
  const sendJson = useCallback((event: string, data: any) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ event, data }));
      return true;
    }
    console.warn("[useWebSocket] No se puede enviar JSON, socket cerrado.");
    return false;
  }, []);

  return {
    connect,
    disconnect,
    sendBinary,
    sendJson,
    lastTelemetry,
    lastAdvice,
    lastAlert,
    lastPending,
    lastStrategy,
  };
}

export default useWebSocket;

