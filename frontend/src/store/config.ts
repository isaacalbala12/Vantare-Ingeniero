import { create } from "zustand";

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
export interface MessageRecord {
  sender: "pilot" | "engineer";
  text: string;
  timestamp: number;
}

export interface RadioState {
  mode: RadioMode;
  currentTokens: string;
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
  setLatestAdvice: (advice: string) => void;
  setLatestAlert: (alert: string) => void;
  setMicLevel: (level: number) => void;
  
  updateTelemetry: (data: Partial<TelemetryState>) => void;
  updateConfig: (newConfig: Partial<AppConfig>) => void;
  applyProfileConfig: (config: AppConfig) => void;
  setScreen: (screen: Screen) => void;
}

// Cargar configuración de localStorage en el arranque si existe
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
        pttHotkey: parsed.pttHotkey ?? "Ctrl+Shift+Space",
        pttStopHotkey: parsed.pttStopHotkey ?? "Ctrl+Shift+Space",
        wakeWordEnabled: parsed.wakeWordEnabled ?? true,
        swearyMessages: parsed.swearyMessages ?? false,
        spotterOffQualifying: parsed.spotterOffQualifying ?? true,
        spotterExcludeStopped: parsed.spotterExcludeStopped ?? true,
        mqttEnabled: parsed.mqttEnabled ?? false,
        mqttBroker: parsed.mqttBroker ?? "localhost",
        mqttPort: parsed.mqttPort ?? 1883,
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
    pttHotkey: "Ctrl+Shift+Space",
    pttStopHotkey: "Ctrl+Shift+Space",
    wakeWordEnabled: true,
    swearyMessages: false,
    spotterOffQualifying: true,
    spotterExcludeStopped: true,
    mqttEnabled: false,
    mqttBroker: "localhost",
    mqttPort: 1883,
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
    set((state) => ({
      radio: {
        ...state.radio,
        messageHistory: [
          ...state.radio.messageHistory,
          { sender, text, timestamp: Date.now() },
        ],
      },
    })),
  setLatestAdvice: (advice) =>
    set((state) => ({
      radio: { ...state.radio, latestAdvice: advice },
    })),
  setLatestAlert: (alert) =>
    set((state) => ({
      radio: { ...state.radio, latestAlert: alert },
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
      return { config: updated };
    }),
  applyProfileConfig: (config) =>
    set(() => {
      try {
        localStorage.setItem("vantare_config", JSON.stringify(config));
      } catch (e) {
        console.error("Fallo al guardar perfil en localStorage:", e);
      }
      return { config };
    }),
  setScreen: (screen) => set({ screen }),
}));
