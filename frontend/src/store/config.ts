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
export type InterruptThreshold = "NEVER" | "SPOTTER" | "CRITICAL" | "IMPORTANT";

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
  licenseKey: string;
  interruptThreshold: InterruptThreshold;
  chiefVoice: string;
  spotterVoice: string;
  chiefRate: number;
  spotterRate: number;
  chiefPitch: number;
  spotterPitch: number;
  spotterVolumeBoost: number;
  audioOutputDevice: string;
  autoVerbosityEnabled: boolean;
  spotterGapForClear: number;
  spotterOverlapDelay: number;
  spotterClearDelay: number;
  spotterRepeatFrequency: number;
  spotterMinSpeed: number;
  spotterMaxClosingSpeed: number;
  spotterEnable3Wide: boolean;
  fcyStopSpotter: boolean;
  driverName: string;
  workerUrl: string;
  enableTemplates: boolean;
}

// --- DOMINIO 5: CREWCHIEF ---
export interface CrewchiefAlert {
  id: string;
  severity: "low" | "medium" | "high" | "critical";
  message: string;
  category: string;
  subtype?: string;
  audioPriority?: number;
  payload?: Record<string, unknown>;
  timestamp: number;
}

export interface CrewchiefState {
  events: CrewchiefAlert[];
  latestByCategory: Record<string, CrewchiefAlert>;
}

// --- INTERFAZ GLOBAL DEL STORE ---
export type Screen = "dashboard" | "config";

export interface GlobalStore {
  connectivity: ConnectivityState;
  radio: RadioState;
  telemetry: TelemetryState;
  config: AppConfig;
  screen: Screen;
  crewchief: CrewchiefState;

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
  setScreen: (screen: Screen) => void;
  pushCrewchiefAlert: (alert: Omit<CrewchiefAlert, 'id' | 'timestamp'>) => void;
  clearCrewchiefAlerts: () => void;
}

// Defaults (single source of truth)
const DEFAULT_CONFIG: AppConfig = {
  vllmIP: "localhost",
  serverPort: 8008,
  micDevice: "default",
  speakerDevice: "default",
  wakeWord: "ingeniero",
  sensitivity: 50,
  pttHotkey: "Ctrl+Shift+Space",
  pttStopHotkey: "Ctrl+Shift+Space",
  wakeWordEnabled: true,
  licenseKey: "",
  interruptThreshold: "SPOTTER",
  chiefVoice: "es-ES-AlvaroNeural",
  spotterVoice: "es-MX-JorgeNeural",
  chiefRate: 0,
  spotterRate: 5,
  chiefPitch: 0,
  spotterPitch: 5,
  spotterVolumeBoost: 20,
  audioOutputDevice: "",
  autoVerbosityEnabled: true,
  spotterGapForClear: 5.0,
  spotterOverlapDelay: 300,
  spotterClearDelay: 500,
  spotterRepeatFrequency: 3.0,
  spotterMinSpeed: 5.0,
  spotterMaxClosingSpeed: 30.0,
  spotterEnable3Wide: true,
  fcyStopSpotter: true,
  driverName: "",
  workerUrl: "https://vantare-llm-proxy.workers.dev",
  enableTemplates: true,
};

/** Patrón de formato de clave de licencia beta: VNT-BETA-XXXX-XXXX-X */
const LICENSE_KEY_REGEX = /^VNT-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]$/i;

/** Valida que una clave de licencia cumpla el formato esperado */
export const isValidLicenseFormat = (key: string): boolean => LICENSE_KEY_REGEX.test(key);

// Cargar configuración de localStorage en el arranque si existe
const loadSavedConfig = (): AppConfig => {
  try {
    let saved = localStorage.getItem("vantare_config");
    if (saved) {
      const parsed = JSON.parse(saved);
      const merged: AppConfig = { ...DEFAULT_CONFIG };
      for (const key of Object.keys(DEFAULT_CONFIG)) {
        if (key in parsed && parsed[key] !== undefined) {
          (merged as any)[key] = parsed[key];
        }
      }
      return merged;
    }
  } catch (e) {
    console.warn("Fallo al leer localStorage para la configuración:", e);
  }
  return { ...DEFAULT_CONFIG };
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
  crewchief: {
    events: [],
    latestByCategory: {},
  },

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
  setScreen: (screen) => set({ screen }),
  pushCrewchiefAlert: (alert) =>
    set((state) => {
      const id = `cc-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      const entry = { ...alert, id, timestamp: Date.now() };
      return {
        crewchief: {
          events: [...state.crewchief.events, entry].slice(-50),
          latestByCategory: {
            ...state.crewchief.latestByCategory,
            [alert.category]: entry,
          },
        },
      };
    }),
  clearCrewchiefAlerts: () =>
    set({ crewchief: { events: [], latestByCategory: {} } }),
}));
