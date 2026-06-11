import { useEffect, useRef, useState, useCallback } from "react";
import { useAppStore } from "../store/config";
import { audioQueue } from "../services/audioQueue";
import { encodeMsgpack, decodeMsgpack, computeDelta, SNAPSHOT_INTERVAL } from "../services/msgpack";
import { evaluateAlertTts, evaluateAdviceTts, evaluateCommentaryTts, logTtsBlocked, shouldDiscardTtsPlayback as shouldDiscardPlayback } from "../services/ttsPlaybackGate";
import { createTtsPipeline } from "../services/ttsPipeline";
import { classifyTtsPriority, type TtsPriority } from "../services/spotterPhrases";
import { spotterPrefetchPhrases } from "../services/spotterPhraseResolver";
import { buildConfigUpdatePayload } from "../services/configUpdatePayload";
import { registerConfigWs } from "../services/configUpdateWs";
import { registerWsCommands } from "../services/wsCommands";
import { getHealth } from "../services/api";
import { buildVoiceHash, ttsCache } from "../services/ttsCache";
import { gapsFromCompetitorPace, gapsFromNativeFrame, mapSidecarBinaryFrame } from "../services/telemetryFrame";
import { expiresAtFromPayload, delayedUntilFromPayload, validationKeyFromPayload } from "../services/alertExpiry";
import { isInternalRadioText } from "../hub/forms/telemetryFilters";
import {
  flattenAlertPayload,
  shouldVoiceAlert,
  shouldVoiceDuringSpeakOnly,
  shouldVoiceForServiceToggle,
} from "../services/alertVoice";
import {
  handleBackendVoicePlaybackEnd,
  handleBackendVoicePlaybackStart,
} from "../services/backendVoiceOverlay";

function shouldSpeakAdvice(text: string): boolean {
  return text.length > 0 && !isInternalRadioText(text);
}

const TTS_RECONNECT_GRACE_MS = 3_000;
const TELEMETRY_UI_INTERVAL_MS = 200; // 5 Hz — evita re-render a 20 Hz

function extractBrakePressure(frame: Record<string, unknown> | null | undefined): number {
  if (!frame) return 0;
  const player = frame.player as Record<string, unknown> | undefined;
  const controls = frame.controls as Record<string, unknown> | undefined;
  const raw = frame.brake ?? frame.brake_pressure ?? player?.brake ?? controls?.brake;
  const value = Number(raw ?? 0);
  return Number.isFinite(value) ? value : 0;
}

function shouldDeferForBraking(priority: TtsPriority, cfg: ReturnType<typeof useAppStore.getState>["config"], frame: Record<string, unknown> | null | undefined): boolean {
  return priority === "NORMAL" && Boolean(cfg.brakingZonesMute) && extractBrakePressure(frame) >= 0.15;
}

function resolveTtsVoice(role: "engineer" | "spotter", cfg: ReturnType<typeof useAppStore.getState>["config"]): string {
  return role === "spotter"
    ? (cfg.ttsVoiceSpotter || "es-ES-ElviraNeural")
    : (cfg.ttsVoiceEngineer || "es-ES-AlvaroNeural");
}

function spotterVoiceRoleForAlert(payload?: Record<string, unknown>): "engineer" | "spotter" {
  const category = String(payload?.category ?? "").toLowerCase();
  if (category === "proximity" || category === "limiter" || category === "damage") {
    return "spotter";
  }
  return "engineer";
}

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
    addRadioAlertToHistory,
    setLatestAdvice,
    setLatestAlert,
    updateConfig,
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
  const ttsPipelineRef = useRef<ReturnType<typeof createTtsPipeline> | null>(null);
  const ttsReconnectGraceUntilRef = useRef<number>(0);
  const latestTelemetryRef = useRef<any>(null);
  const lastTelemetryUiUpdateRef = useRef<number>(0);
  const pendingTelemetryFlushRef = useRef<number | null>(null);
  const binarySeqRef = useRef<number>(0);
  const lastAppliedBinarySeqRef = useRef<number>(0);
  const lastAppliedBinaryTimeRef = useRef<number>(Number.NEGATIVE_INFINITY);
  const serverTelemetryActiveRef = useRef<boolean>(false);
  const pendingAdviceTokensRef = useRef<string>("");
  const lastAdviceTokenUiRef = useRef<number>(0);
  const previousFrameRef = useRef<Record<string, unknown> | null>(null);
  const frameCountRef = useRef<number>(0);

  // Guardar referencias del store para evitar recrear funciones
  const currentTokensRef = useRef("");
  useEffect(() => {
    // Suscribirse a los tokens actuales en el store
    const unsub = useAppStore.subscribe((state) => {
      currentTokensRef.current = state.radio.currentTokens;
    });
    return unsub;
  }, []);

  const clearPendingTts = useCallback(() => {
    const pipeline = ttsPipelineRef.current;
    pipeline?.clearQueueKeepImmediate();
    if (pipeline?.getCurrentPriority() !== "ENGINEER" && pipeline?.isProcessing()) {
      pipeline.abortProcessingIntentional();
    }
    audioQueue.stopNormal();
  }, []);

  const clearPendingEngineerTts = useCallback(() => {
    const pipeline = ttsPipelineRef.current;
    pipeline?.clearQueueKeepImmediate();
    if (pipeline?.getCurrentPriority() !== "IMMEDIATE" && pipeline?.isProcessing()) {
      pipeline.abortProcessingIntentional();
    }
    audioQueue.stopEngineer();
  }, []);

  const prefetchSpotterTts = useCallback(async () => {
    const configState = useAppStore.getState().config;
    const baseUrl = `http://${configState.vllmIP || "127.0.0.1"}:${configState.serverPort || 8008}`;
    const spotterVoice = resolveTtsVoice("spotter", configState);
    const voiceHash = buildVoiceHash({
      ttsBackend: configState.ttsBackend,
      ttsVoice: spotterVoice,
      role: "spotter",
      profileId: configState.personalityProfileId,
    });
    await ttsCache.prefetch(spotterPrefetchPhrases(configState.personalityProfileId), voiceHash, async (text) => {
      try {
        const res = await fetch(
          `${baseUrl}/tts?text=${encodeURIComponent(text)}&voice=${encodeURIComponent(spotterVoice)}`,
        );
        if (!res.ok) return null;
        return await res.blob();
      } catch {
        return null;
      }
    });
  }, []);

  const processTtsQueueRef = useRef<() => void>(() => {});

  useEffect(() => {
    ttsPipelineRef.current = createTtsPipeline({
      deferFinishUntilPlaybackIdle: true,
      fetchTts: async (text, voice, signal) => {
        const configState = useAppStore.getState().config;
        const baseUrl = `http://${configState.vllmIP || "127.0.0.1"}:${configState.serverPort || 8008}`;
        const res = await fetch(
          `${baseUrl}/tts?text=${encodeURIComponent(text)}&voice=${encodeURIComponent(voice)}`,
          { signal },
        );
        if (!res.ok) throw new Error(`TTS returned ${res.status}`);
        return await res.blob();
      },
      getVoice: (role) => resolveTtsVoice(role, useAppStore.getState().config),
      getVoiceHash: (params) => buildVoiceHash({
        ttsBackend: params.ttsBackend,
        ttsVoice: params.ttsVoice,
        role: params.role as "engineer" | "spotter",
        profileId: params.profileId,
      }),
      getCache: () => ttsCache,
      getAudioQueue: () => audioQueue,
      shouldDiscard: shouldDiscardPlayback,
      getRadioMode: () => useAppStore.getState().radio.mode,
      getConfig: () => useAppStore.getState().config as unknown as Record<string, unknown>,
      shouldDeferItem: (item) => {
        const cfg = useAppStore.getState().config;
        return (
          shouldDeferForBraking(item.priority, cfg, latestTelemetryRef.current) ||
          (typeof item.delayedUntilMs === "number" && item.delayedUntilMs > performance.now())
        );
      },
    });

    audioQueue.setOnIdle(() => {
      if (ttsPipelineRef.current?.isProcessing()) {
        ttsPipelineRef.current.finish();
      }
    });

    processTtsQueueRef.current = () => {
      void ttsPipelineRef.current?.processNext();
    };
  }, []);

  const enqueueTtsText = useCallback((
    text: string,
    source = "unknown",
    priority: TtsPriority = "NORMAL",
    payload?: Record<string, unknown>,
    voiceRole: "engineer" | "spotter" = "engineer",
  ): boolean => {
    const trimmed = text.trim();
    if (!trimmed || !shouldSpeakAdvice(trimmed)) {
      return false;
    }

    const resolvedPriority: TtsPriority =
      priority === "ENGINEER"
        ? "ENGINEER"
        : payload
          ? classifyTtsPriority(trimmed, payload)
          : priority;

    const cfg = useAppStore.getState().config;
    let delayedUntilMs = delayedUntilFromPayload(payload);
    if (shouldDeferForBraking(resolvedPriority, cfg, latestTelemetryRef.current)) {
      delayedUntilMs = performance.now() + 300;
    }

    const resolvedVoiceRole = source === "alert" ? spotterVoiceRoleForAlert(payload) : voiceRole;
    const pipeline = ttsPipelineRef.current;
    if (!pipeline) return false;

    return pipeline.enqueue({
      text: trimmed,
      priority: resolvedPriority,
      source,
      voiceRole: resolvedVoiceRole,
      expiresAt: expiresAtFromPayload(payload),
      delayedUntilMs,
      validationKey: validationKeyFromPayload(payload),
    });
  }, []);

  const connect = useCallback(() => {
    if (socketRef.current && (socketRef.current.readyState === WebSocket.CONNECTING || socketRef.current.readyState === WebSocket.OPEN)) {
      return;
    }

    manuallyClosedRef.current = false;
    setWsStatus("CONNECTING");

    // Construir la URL con el IP y puerto del store
    const vllmIP = config.vllmIP || "127.0.0.1";
    const serverPort = config.serverPort || 8008;
    const wsUrl = `ws://${vllmIP}:${serverPort}/ws`;

    console.log(`[useWebSocket] Conectando a ${wsUrl}...`);

    const flushTelemetryToUi = (decoded: Record<string, unknown>) => {
      const mapped = mapSidecarBinaryFrame(decoded);
      const nativeGaps = gapsFromNativeFrame(decoded);
      setLastTelemetry(decoded);
      updateTelemetry({
        ...mapped,
        ...(nativeGaps ? { gaps: nativeGaps } : {}),
      });
    };

    const flushPendingTelemetryNow = () => {
      if (pendingTelemetryFlushRef.current !== null) {
        clearTimeout(pendingTelemetryFlushRef.current);
        pendingTelemetryFlushRef.current = null;
      }
      const latest = latestTelemetryRef.current as Record<string, unknown> | null;
      if (!latest) {
        return;
      }
      lastTelemetryUiUpdateRef.current = performance.now();
      flushTelemetryToUi(latest);
    };

    const scheduleTrailingTelemetryFlush = () => {
      if (pendingTelemetryFlushRef.current !== null) {
        return;
      }
      const elapsed = performance.now() - lastTelemetryUiUpdateRef.current;
      const delay = Math.max(0, TELEMETRY_UI_INTERVAL_MS - elapsed);
      pendingTelemetryFlushRef.current = window.setTimeout(() => {
        pendingTelemetryFlushRef.current = null;
        const latest = latestTelemetryRef.current as Record<string, unknown> | null;
        if (!latest) {
          return;
        }
        lastTelemetryUiUpdateRef.current = performance.now();
        flushTelemetryToUi(latest);
      }, delay);
    };

    const applyBinaryTelemetry = (buffer: ArrayBuffer, seq: number) => {
      serverTelemetryActiveRef.current = true;
      try {
        const decoded: Record<string, unknown> = decodeMsgpack(new Uint8Array(buffer));
        const frameTime = typeof decoded._t === "number" ? decoded._t : Number.NaN;
        const seqIsFresh = seq >= lastAppliedBinarySeqRef.current;
        const timeIsFresh = Number.isFinite(frameTime) && frameTime >= lastAppliedBinaryTimeRef.current;
        if (!seqIsFresh && !timeIsFresh) {
          return;
        }

        lastAppliedBinarySeqRef.current = Math.max(lastAppliedBinarySeqRef.current, seq);
        if (Number.isFinite(frameTime)) {
          lastAppliedBinaryTimeRef.current = Math.max(lastAppliedBinaryTimeRef.current, frameTime);
        }
        latestTelemetryRef.current = decoded;

        const now = performance.now();
        if (now - lastTelemetryUiUpdateRef.current < TELEMETRY_UI_INTERVAL_MS) {
          scheduleTrailingTelemetryFlush();
          return;
        }

        lastTelemetryUiUpdateRef.current = now;
        flushTelemetryToUi(decoded);
      } catch (e) {
        console.error("[useWebSocket] Error decoding MessagePack:", e);
      }
    };

    try {
      const ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";
      socketRef.current = ws;

      ws.onopen = () => {
        console.log("[useWebSocket] Conectado exitosamente.");
        setWsStatus("CONNECTED");
        reconnectDelayRef.current = 1000; // Resetear backoff
        ttsReconnectGraceUntilRef.current = performance.now() + TTS_RECONNECT_GRACE_MS;
        clearPendingTts();
        ttsPipelineRef.current?.clearSpokenCooldown();
        void prefetchSpotterTts();
        serverTelemetryActiveRef.current = false;
        binarySeqRef.current = 0;
        lastAppliedBinarySeqRef.current = 0;
        lastAppliedBinaryTimeRef.current = Number.NEGATIVE_INFINITY;
        if (pendingTelemetryFlushRef.current !== null) {
          clearTimeout(pendingTelemetryFlushRef.current);
          pendingTelemetryFlushRef.current = null;
        }
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
        const cfg = useAppStore.getState().config;
        registerConfigWs(ws);
        registerWsCommands(ws);
        ws.send(JSON.stringify({
          event: "config_update",
          data: buildConfigUpdatePayload(cfg),
        }));
        // Reset delta tracking on reconnect
        previousFrameRef.current = null;
        frameCountRef.current = 0;
      };

      ws.onmessage = (event) => {
        // Binary telemetry (MessagePack @ 20 Hz). Electron may deliver Blob unless binaryType is set.
        if (event.data instanceof ArrayBuffer) {
          const seq = ++binarySeqRef.current;
          applyBinaryTelemetry(event.data, seq);
          return;
        }
        if (typeof Blob !== "undefined" && event.data instanceof Blob) {
          const seq = ++binarySeqRef.current;
          void event.data.arrayBuffer().then((buffer) => applyBinaryTelemetry(buffer, seq));
          return;
        }

        // Handle text JSON (all other events: strategy, advice, alert, etc)
        let parsed: any;
        try {
          parsed = JSON.parse(event.data);
        } catch (e) {
          console.error("[useWebSocket] Error parsing JSON:", e);
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
            latestTelemetryRef.current = payload;
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
            });
            break;
          }

          case "strategy": {
            setLastStrategy(payload);
            if (payload.fuel) {
              updateTelemetry({
                fuel: Number(payload.fuel.fuel_in_tank ?? 0),
              });
            }
            if (Array.isArray(payload.competitors) && payload.competitors.length > 0) {
              const native = gapsFromNativeFrame(payload);
              const gaps = native ?? gapsFromCompetitorPace(payload.competitors);
              updateTelemetry({ gaps });
            }
            if (payload.advice) {
              setLatestAdvice(payload.advice);
            }
            break;
          }

          case "llm_pending": {
            setLastPending(payload);
            const mode = useAppStore.getState().radio.mode;
            const speakOnly = useAppStore.getState().config.speakOnlyWhenSpokenTo;
            const pttFlow = mode === "LISTENING_PILOT" || mode === "THINKING_LLM";
            if (pttFlow || !speakOnly) {
              setRadioMode("THINKING_LLM");
            }
            break;
          }

          case "advice_start": {
            clearPendingEngineerTts();
            setLastAdvice(payload);
            const mode = useAppStore.getState().radio.mode;
            const speakOnly = useAppStore.getState().config.speakOnlyWhenSpokenTo;
            const pttFlow = mode === "LISTENING_PILOT" || mode === "THINKING_LLM";
            if (pttFlow || !speakOnly) {
              setRadioMode("THINKING_LLM");
            }
            setCurrentTokens("");
            break;
          }

          case "advice_token": {
            const token = payload.token || "";
            pendingAdviceTokensRef.current += token;
            const now = performance.now();
            if (now - lastAdviceTokenUiRef.current >= 100) {
              lastAdviceTokenUiRef.current = now;
              setCurrentTokens(currentTokensRef.current + pendingAdviceTokensRef.current);
              pendingAdviceTokensRef.current = "";
            }
            break;
          }

          case "advice_end": {
            if (pendingAdviceTokensRef.current) {
              setCurrentTokens(currentTokensRef.current + pendingAdviceTokensRef.current);
              pendingAdviceTokensRef.current = "";
            }
            const fullText = payload.full_text || "";
            const showInUi = fullText && !isInternalRadioText(fullText);
            if (!fullText.trim()) {
              setLatestAdvice("No he recibido respuesta del ingeniero. Repite la pregunta.");
            } else if (showInUi) {
              setLatestAdvice(fullText);
              addMessageToHistory("engineer", fullText);
            }
            setCurrentTokens("");

            const inReconnectGrace = performance.now() < ttsReconnectGraceUntilRef.current;
            const speakOnly = useAppStore.getState().config.speakOnlyWhenSpokenTo;

            // Unified gate — evaluateAdviceTts handles all checks
            const adviceDecision = evaluateAdviceTts({
              fullText,
              speakOnlyWhenSpokenTo: speakOnly,
              inReconnectGrace,
            });

            if (!adviceDecision.allow) {
              logTtsBlocked("advice_end", adviceDecision.reason, { speakOnlyWhenSpokenTo: speakOnly });
              setRadioMode("IDLE");
              break;
            }

            const willSpeak =
              showInUi &&
              enqueueTtsText(fullText, "advice", "ENGINEER", undefined, "engineer");

            if (!willSpeak) {
              logTtsBlocked("advice_end", "enqueue_failed_or_empty", { speakOnlyWhenSpokenTo: speakOnly });
            }

            if (willSpeak) {
              processTtsQueueRef.current();
            } else {
              setRadioMode("IDLE");
            }
            break;
          }

          case "commentary_end": {
            const commentaryText = payload.full_text || "";
            const showInUi = commentaryText && !isInternalRadioText(commentaryText);
            if (showInUi) {
              setLatestAdvice(commentaryText);
              addMessageToHistory("engineer", commentaryText);
            }
            const inReconnectGrace = performance.now() < ttsReconnectGraceUntilRef.current;
            const speakOnlyCommentary = useAppStore.getState().config.speakOnlyWhenSpokenTo;
            const engineerEnabled = useAppStore.getState().config.engineerEnabled;

            // Unified gate — evaluateCommentaryTts handles all checks
            const commentaryDecision = evaluateCommentaryTts({
              fullText: commentaryText,
              speakOnlyWhenSpokenTo: speakOnlyCommentary,
              engineerEnabled,
              inReconnectGrace,
            });

            if (!commentaryDecision.allow) {
              logTtsBlocked("commentary_end", commentaryDecision.reason, {
                speakOnlyWhenSpokenTo: speakOnlyCommentary,
                engineerEnabled,
              });
              setRadioMode("IDLE");
              break;
            }

            const willSpeak =
              showInUi &&
              enqueueTtsText(commentaryText, "commentary", "ENGINEER", payload, "engineer");

            if (willSpeak) {
              processTtsQueueRef.current();
            } else {
              setRadioMode("IDLE");
            }
            break;
          }

          case "voice_playback_start":
            handleBackendVoicePlaybackStart(payload);
            break;

          case "voice_playback_end":
            handleBackendVoicePlaybackEnd(payload);
            break;

          case "config_ack": {
            const ackCfg = payload.config ?? payload;
            if (ackCfg && typeof ackCfg === "object") {
              const patch: Record<string, unknown> = {};
              if (typeof ackCfg.personalityProfileId === "string") {
                patch.personalityProfileId = ackCfg.personalityProfileId;
              }
              if (typeof ackCfg.verbosityLevel === "string") {
                patch.verbosityLevel = ackCfg.verbosityLevel;
              }
              if (typeof ackCfg.brakingZonesMute === "boolean") {
                patch.brakingZonesMute = ackCfg.brakingZonesMute;
              }
              if (typeof ackCfg.swearyMessages === "boolean") {
                patch.swearyMessages = ackCfg.swearyMessages;
              }
              if (typeof ackCfg.speakOnlyWhenSpokenTo === "boolean") {
                patch.speakOnlyWhenSpokenTo = ackCfg.speakOnlyWhenSpokenTo;
              }
              if (typeof ackCfg.spotterClearDelayS === "number") {
                patch.spotterClearDelayS = ackCfg.spotterClearDelayS;
              }
              if (typeof ackCfg.spotterOverlapDelayS === "number") {
                patch.spotterOverlapDelayS = ackCfg.spotterOverlapDelayS;
              }
              if (typeof ackCfg.spotterHoldRepeatS === "number") {
                patch.spotterHoldRepeatS = ackCfg.spotterHoldRepeatS;
              }
              if (typeof ackCfg.spotterGapFrequencyS === "number") {
                patch.spotterGapFrequencyS = ackCfg.spotterGapFrequencyS;
              }
              if (typeof ackCfg.spotterCarLengthM === "number") {
                patch.spotterCarLengthM = ackCfg.spotterCarLengthM;
              }
              if (typeof ackCfg.spotterMinSpeedMs === "number") {
                patch.spotterMinSpeedMs = ackCfg.spotterMinSpeedMs;
              }
              if (typeof ackCfg.spotterRaceStartDelayS === "number") {
                patch.spotterRaceStartDelayS = ackCfg.spotterRaceStartDelayS;
              }
              if (typeof ackCfg.spotterOffQualifying === "boolean") {
                patch.spotterOffQualifying = ackCfg.spotterOffQualifying;
              }
              if (typeof ackCfg.spotterExcludeStopped === "boolean") {
                patch.spotterExcludeStopped = ackCfg.spotterExcludeStopped;
              }
              if (typeof ackCfg.spotterEnabled === "boolean") {
                patch.spotterEnabled = ackCfg.spotterEnabled;
              }
              if (typeof ackCfg.engineerEnabled === "boolean") {
                patch.engineerEnabled = ackCfg.engineerEnabled;
              }
              if (typeof ackCfg.proactivityLevel === "string") {
                patch.proactivityLevel = ackCfg.proactivityLevel;
              }
              if (typeof ackCfg.pearlFrequency === "number") {
                patch.pearlFrequency = ackCfg.pearlFrequency;
              }
              if (typeof ackCfg.voiceBackendPlayback === "boolean") {
                patch.voiceBackendPlayback = ackCfg.voiceBackendPlayback;
              }
              if (Object.keys(patch).length > 0) {
                updateConfig(patch);
              }
            }
            break;
          }

          case "alert": {
            setLastAlert(payload);
            const alertMsg = payload.message || "";
            setLatestAlert(alertMsg);

            const prevAlerts = useAppStore.getState().telemetry.alerts ?? [];
            updateTelemetry({
              alerts: [alertMsg, ...prevAlerts.filter((a) => a !== alertMsg)].slice(0, 5),
            });

            const category = String(payload.category || "").toLowerCase();
            const isPttResponse =
              category === "voice_response" || payload.fast_command === true;

            if (isPttResponse && alertMsg && !isInternalRadioText(alertMsg)) {
              setLatestAdvice(alertMsg);
              addMessageToHistory("engineer", alertMsg);
            }

            // Historial: criterio de voz UI (independiente de backend playback)
            const { speakOnlyWhenSpokenTo, spotterEnabled, engineerEnabled, voiceBackendPlayback } =
              useAppStore.getState().config;
            const voicePayload = flattenAlertPayload(payload);
            const shouldLogRadioHistory =
              Boolean(alertMsg) &&
              !isInternalRadioText(alertMsg) &&
              shouldVoiceAlert(voicePayload) &&
              shouldVoiceDuringSpeakOnly(speakOnlyWhenSpokenTo, category, "alert") &&
              shouldVoiceForServiceToggle(category, spotterEnabled, engineerEnabled, voicePayload);

            const ttsDecision = evaluateAlertTts({
              message: alertMsg,
              payload,
              speakOnlyWhenSpokenTo,
              spotterEnabled,
              engineerEnabled,
              voiceBackendPlayback,
            });

            const spotterCategories = new Set([
              "proximity", "pit_limiter", "fuel", "safety_car", "damage", "puncture", "impact", "limiter",
            ]);
            if (shouldLogRadioHistory) {
              if (spotterCategories.has(category)) {
                addRadioAlertToHistory("spotter", alertMsg, category);
              } else if (category !== "voice_response" && category !== "system" && category !== "spotter") {
                addRadioAlertToHistory("engineer", alertMsg, category);
              }
            }

            const voiceOk = ttsDecision.allow;
            if (!voiceOk && ttsDecision.reason !== "backend_playback") {
              logTtsBlocked("alert", ttsDecision.reason, {
                category,
                speakOnlyWhenSpokenTo,
                spotterEnabled,
                engineerEnabled,
              });
            }
            const alertPriority: TtsPriority = isPttResponse ? "ENGINEER" : "IMMEDIATE";
            const alertVoiceRole: "engineer" | "spotter" = isPttResponse
              ? "engineer"
              : spotterVoiceRoleForAlert(payload);
            if (alertMsg && voiceOk && enqueueTtsText(alertMsg, "alert", alertPriority, payload, alertVoiceRole)) {
              processTtsQueueRef.current();
            } else if (isPttResponse) {
              setRadioMode("IDLE");
            }
            break;
          }

          default:
            console.log("[useWebSocket] Evento desconocido:", eventType, payload);
        }
      };

      ws.onclose = (event) => {
        serverTelemetryActiveRef.current = false;
        flushPendingTelemetryNow();
        registerConfigWs(null);
        registerWsCommands(null);
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
    clearPendingTts,
    prefetchSpotterTts,
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

  // Esperar a que el backend responda /health antes del primer WebSocket (arranque empaquetado ~20s)
  useEffect(() => {
    let cancelled = false;
    let waitTimer: number | null = null;

    const waitThenConnect = async () => {
      while (!cancelled) {
        const health = await getHealth();
        if (cancelled) return;
        if (health?.status === "ok") {
          connect();
          return;
        }
        await new Promise<void>((resolve) => {
          waitTimer = window.setTimeout(resolve, 1500);
        });
      }
    };

    void waitThenConnect();

    return () => {
      cancelled = true;
      if (waitTimer !== null) {
        clearTimeout(waitTimer);
        waitTimer = null;
      }
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

  // Solo reenviar telemetría si el backend no nos la está empujando (modo sin sidecar)
  useEffect(() => {
    const interval = setInterval(() => {
      if (serverTelemetryActiveRef.current) return;
      const frame = latestTelemetryRef.current;
      if (!frame || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) return;

      const isFull = frameCountRef.current % SNAPSHOT_INTERVAL === 0;
      const delta = computeDelta(frame, previousFrameRef.current, isFull);
      const binary = encodeMsgpack(delta);
      socketRef.current.send(binary.buffer);

      previousFrameRef.current = frame;
      frameCountRef.current++;
    }, 50);

    return () => clearInterval(interval);
  }, [sendJson]);

  return {
    connect,
    disconnect,
    sendBinary,
    sendJson,
    clearPendingTts,
    lastTelemetry,
    lastAdvice,
    lastAlert,
    lastPending,
    lastStrategy,
  };
}

export default useWebSocket;

