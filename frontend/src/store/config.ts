import { create } from "zustand";
import { migrateTtsVolumePercent } from "../hub/forms/volumeMigration";
import { isInternalRadioText } from "../hub/forms/telemetryFilters";
import { getPlatform } from "../core/platform";

export type WebSocketStatus = "CONNECTING" | "CONNECTED" | "DISCONNECTED";
export type RadioMode = "IDLE" | "LISTENING_PILOT" | "THINKING_LLM" | "SPEAKING_ENGINE";

// --- DOMINIO 1: CONECTIVIDAD ---
export interface ConnectivityState {
  wsStatus: WebSocketStatus;
  latency: number;
  backendHealth: {
    shared_memory: boolean;
    lmu_api: boolean;
    llm: boolean;
    websocket: boolean;
  } | null;
}

// --- DOMINIO 2: RADIO E INGENIERO ---
export type HistorySender = "pilot" | "engineer" | "spotter";

export interface MessageRecord {
  sender: HistorySender;
  text: string;
  timestamp: number;
  category?: string;
}

export interface RadioState {
  mode: RadioMode;
  currentTokens: string;
  voicePlaybackText: string;
  messageHistory: MessageRecord[];
  latestAdvice: string;
  latestAlert: string;
  micLevel: number;
}

// --- DOMINIO 3: TELEMETRÍA (20Hz) ---
export interface TelemetryState {
  speed: number;
  rpm: number;
  gear: number;
  fuel: number;
  lap: number;
  position: number;
  gaps: {
    ahead: number;
    behind: number;
  };
  tyreWear: {
    fl: number;
    fr: number;
    rl: number;
    rr: number;
  };
  alerts: string[];
}

// --- DOMINIO 4: CONFIGURACIÓN ---
export interface AppConfig {
  vllmIP: string;
  serverPort: number;
  micDevice: string;
  speakerDevice: string;
  wakeWord: string;
  sensitivity: number;
  pttHotkey: string;
  pttStopHotkey: string;
  wakeWordEnabled: boolean;
  swearyMessages: boolean;
  spotterOffQualifying: boolean;
  spotterExcludeStopped: boolean;
  mqttEnabled: boolean;
  mqttBroker: string;
  mqttPort: number;
  personalityProfileId: "formal" | "standard" | "aggressive";
  verbosityLevel: "silent" | "normal" | "detailed";
  ttsVoiceEngineer: string;
  ttsVoiceSpotter: string;
  ttsBackend: string;
  spotterClearDelayS: number;
  spotterOverlapDelayS: number;
  spotterHoldRepeatS: number;
  spotterGapFrequencyS: number;
  spotterCarLengthM: number;
  spotterMinSpeedMs: number;
  spotterRaceStartDelayS: number;
  brakingZonesMute: boolean;
  speakOnlyWhenSpokenTo: boolean;
  ttsVolumeBoost: number;
  spotterEnabled: boolean;
  engineerEnabled: boolean;
}

// --- INTERFAZ GLOBAL DEL STORE ---
export type Screen = "dashboard" | "config";

export interface GlobalStore {
  connectivity: ConnectivityState;
  radio: RadioState;
  telemetry: TelemetryState;
  config: AppConfig;
  screen: Screen;

  // Acciones
  setWsStatus: (status: WebSocketStatus) => void;
  setLatency: (ms: number) => void;
  setBackendHealth: (health: ConnectivityState["backendHealth"]) => void;
  
  setRadioMode: (mode: RadioMode) => void;
  setCurrentTokens: (tokens: string) => void;
  addMessageToHistory: (sender: "pilot" | "engineer", text: string) => void;
  addRadioAlertToHistory: (sender: "spotter" | "engineer", text: string, category?: string) => void;
  setLatestAdvice: (advice: string) => void;
  setLatestAlert: (alert: string) => void;
  setVoicePlaybackText: (text: string) => void;
  setMicLevel: (level: number) => void;
  
  updateTelemetry: (data: Partial<TelemetryState>) => void;
  updateConfig: (newConfig: Partial<AppConfig>) => void;
  applyProfileConfig: (config: AppConfig) => void;
  setScreen: (screen: Screen) => void;
}

// Cargar configuración de localStorage en el arranque si existe
const DEFAULT_PTT_HOTKEY = "Ctrl+Shift+Space";
const MESSAGE_HISTORY_MAX = 500;

function appendHistoryMessage(
  history: MessageRecord[],
  entry: MessageRecord,
): MessageRecord[] {
  const last = history[history.length - 1];
  if (last?.sender === entry.sender && last.text === entry.text) {
    return history;
  }
  const next = [...history, entry];
  if (next.length <= MESSAGE_HISTORY_MAX) return next;
  return next.slice(next.length - MESSAGE_HISTORY_MAX);
}

/** Migra el atajo legacy "P" (conflictúa al escribir) al default con modificador. */
function normalizePttHotkey(value: string | undefined): string {
  const trimmed = (value ?? DEFAULT_PTT_HOTKEY).trim();
  if (trimmed === "P") return DEFAULT_PTT_HOTKEY;
  return trimmed || DEFAULT_PTT_HOTKEY;
}

const loadSavedConfig = (): AppConfig => {
  try {
    let saved = localStorage.getItem("vantare_config");
    if (saved) {
      const parsed = JSON.parse(saved);
      return {
        vllmIP: parsed.vllmIP ?? "localhost",
        serverPort: parsed.serverPort ?? 8008,
        micDevice: parsed.micDevice ?? "default",
        speakerDevice: parsed.speakerDevice ?? "default",
        wakeWord: parsed.wakeWord ?? "ingeniero",
        sensitivity: parsed.sensitivity ?? 50,
        pttHotkey: normalizePttHotkey(parsed.pttHotkey),
        pttStopHotkey: normalizePttHotkey(parsed.pttStopHotkey),
        wakeWordEnabled: parsed.wakeWordEnabled ?? true,
        swearyMessages: parsed.swearyMessages ?? false,
        spotterOffQualifying: parsed.spotterOffQualifying ?? true,
        spotterExcludeStopped: parsed.spotterExcludeStopped ?? true,
        mqttEnabled: parsed.mqttEnabled ?? false,
        mqttBroker: parsed.mqttBroker ?? "localhost",
        mqttPort: parsed.mqttPort ?? 1883,
        personalityProfileId: parsed.personalityProfileId ?? "standard",
        verbosityLevel: parsed.verbosityLevel ?? "normal",
        ttsVoiceEngineer: parsed.ttsVoiceEngineer ?? "es-ES-AlvaroNeural",
        ttsVoiceSpotter: parsed.ttsVoiceSpotter ?? "es-ES-ElviraNeural",
        ttsBackend: parsed.ttsBackend ?? "edge",
        spotterClearDelayS: parsed.spotterClearDelayS ?? 0.15,
        spotterOverlapDelayS: parsed.spotterOverlapDelayS ?? 2.0,
        spotterHoldRepeatS: parsed.spotterHoldRepeatS ?? parsed.spotterOverlapDelayS ?? 3.0,
        spotterGapFrequencyS: parsed.spotterGapFrequencyS ?? 30,
        spotterCarLengthM: parsed.spotterCarLengthM ?? 4.5,
        spotterMinSpeedMs: parsed.spotterMinSpeedMs ?? 10.0,
        spotterRaceStartDelayS: parsed.spotterRaceStartDelayS ?? 20.0,
        brakingZonesMute: parsed.brakingZonesMute ?? false,
        speakOnlyWhenSpokenTo: parsed.speakOnlyWhenSpokenTo ?? false,
        ttsVolumeBoost: migrateTtsVolumePercent(parsed.ttsVolumeBoost),
        spotterEnabled: parsed.spotterEnabled ?? false,
        engineerEnabled: parsed.engineerEnabled ?? false,
      };
    }
  } catch (e) {
    console.warn("Fallo al leer localStorage para la configuración:", e);
  }
  return {
    vllmIP: "localhost",
    serverPort: 8008,
    micDevice: "default",
    speakerDevice: "default",
    wakeWord: "ingeniero",
    sensitivity: 50,
    pttHotkey: DEFAULT_PTT_HOTKEY,
    pttStopHotkey: DEFAULT_PTT_HOTKEY,
    wakeWordEnabled: true,
    swearyMessages: false,
    spotterOffQualifying: true,
    spotterExcludeStopped: true,
    mqttEnabled: false,
    mqttBroker: "localhost",
    mqttPort: 1883,
    personalityProfileId: "standard",
    verbosityLevel: "normal",
    ttsVoiceEngineer: "es-ES-AlvaroNeural",
    ttsVoiceSpotter: "es-ES-ElviraNeural",
    ttsBackend: "edge",
    spotterClearDelayS: 0.15,
    spotterOverlapDelayS: 2.0,
    spotterHoldRepeatS: 3.0,
    spotterGapFrequencyS: 30,
    spotterCarLengthM: 4.5,
    spotterMinSpeedMs: 10.0,
    spotterRaceStartDelayS: 20.0,
    brakingZonesMute: false,
    speakOnlyWhenSpokenTo: false,
    ttsVolumeBoost: 100,
    spotterEnabled: false,
    engineerEnabled: false,
  };
};

export const useAppStore = create<GlobalStore>((set) => ({
  // Estado Inicial
  connectivity: {
    wsStatus: "DISCONNECTED",
    latency: 0,
    backendHealth: null,
  },
  radio: {
    mode: "IDLE",
    currentTokens: "",
    voicePlaybackText: "",
    messageHistory: [],
    latestAdvice: "",
    latestAlert: "",
    micLevel: 0,
  },
  screen: "dashboard",
  telemetry: {
    speed: 0,
    rpm: 0,
    gear: 0,
    fuel: 0.0,
    lap: 1,
    position: 1,
    gaps: { ahead: 0.0, behind: 0.0 },
    tyreWear: { fl: 100, fr: 100, rl: 100, rr: 100 },
    alerts: [],
  },
  config: loadSavedConfig(),

  // Acciones
  setWsStatus: (status) =>
    set((state) => ({
      connectivity: { ...state.connectivity, wsStatus: status },
    })),
  setLatency: (ms) =>
    set((state) => ({
      connectivity: { ...state.connectivity, latency: ms },
    })),
  setBackendHealth: (health) =>
    set((state) => ({
      connectivity: { ...state.connectivity, backendHealth: health },
    })),

  setRadioMode: (mode) =>
    set((state) => ({
      radio: { ...state.radio, mode },
    })),
  setCurrentTokens: (tokens) =>
    set((state) => ({
      radio: { ...state.radio, currentTokens: tokens },
    })),
  addMessageToHistory: (sender, text) =>
    set((state) => {
      const trimmed = text.trim();
      if (!trimmed || isInternalRadioText(trimmed)) return state;
      return {
        radio: {
          ...state.radio,
          messageHistory: appendHistoryMessage(state.radio.messageHistory, {
            sender,
            text: trimmed,
            timestamp: Date.now(),
          }),
        },
      };
    }),
  addRadioAlertToHistory: (sender, text, category) =>
    set((state) => {
      const trimmed = text.trim();
      if (!trimmed || isInternalRadioText(trimmed)) return state;
      return {
        radio: {
          ...state.radio,
          messageHistory: appendHistoryMessage(state.radio.messageHistory, {
            sender,
            text: trimmed,
            timestamp: Date.now(),
            category,
          }),
        },
      };
    }),
  setLatestAdvice: (advice) =>
    set((state) => ({
      radio: { ...state.radio, latestAdvice: advice },
    })),
  setLatestAlert: (alert) =>
    set((state) => ({
      radio: { ...state.radio, latestAlert: alert },
    })),
  setVoicePlaybackText: (text) =>
    set((state) => ({
      radio: { ...state.radio, voicePlaybackText: text },
    })),
  setMicLevel: (level) =>
    set((state) => ({
      radio: { ...state.radio, micLevel: level },
    })),

  updateTelemetry: (data) =>
    set((state) => ({
      telemetry: { ...state.telemetry, ...data },
    })),
  updateConfig: (newConfig) =>
    set((state) => {
      const updated = { ...state.config, ...newConfig };
      try {
        localStorage.setItem("vantare_config", JSON.stringify(updated));
      } catch (e) {
        console.error("Fallo al guardar en localStorage:", e);
      }
      // Sincronizar hotkeys PTT con Electron si cambian
      if ("pttHotkey" in newConfig || "pttStopHotkey" in newConfig) {
        const platform = getPlatform();
        if (platform.updatePttHotkeys) {
          void platform.updatePttHotkeys({
            start: updated.pttHotkey,
            stop: updated.pttStopHotkey,
          });
        }
      }
      return { config: updated };
    }),
  applyProfileConfig: (config) =>
    set(() => {
      const normalized: AppConfig = {
        ...config,
        ttsVolumeBoost: migrateTtsVolumePercent(config.ttsVolumeBoost),
      };
      try {
        localStorage.setItem("vantare_config", JSON.stringify(normalized));
      } catch (e) {
        console.error("Fallo al guardar perfil en localStorage:", e);
      }
      const platform = getPlatform();
      if (platform.updatePttHotkeys) {
        void platform.updatePttHotkeys({
          start: normalized.pttHotkey,
          stop: normalized.pttStopHotkey,
        });
      }
      return { config: normalized };
    }),
  setScreen: (screen) => set({ screen }),
}));
