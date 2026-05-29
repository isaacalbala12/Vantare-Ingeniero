import { create } from 'zustand';

export type RadioMode = 'IDLE' | 'LISTENING_PILOT' | 'THINKING_LLM' | 'SPEAKING_ENGINE';
export type ConnectionStatus = 'DISCONNECTED' | 'CONNECTING' | 'CONNECTED';

export interface SpotterAlert {
  id: string;
  type: string; // 'pit_limiter', 'tyre_wear', 'fuel_low', etc.
  message: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  timestamp: number;
}

export interface TelemetryData {
  speed: number;
  gear: number;
  rpm: number;
  lapNumber: number;
  fuelInTank: number;
  estimatedLapsRemaining: number;
  fuelNeededToFinish: number;
  wearFL: number;
  wearFR: number;
  wearRL: number;
  wearRR: number;
  sessionTimeLeft: number;
  sessionLapsLeft: number;
}

export interface RadioMessage {
  id: string;
  sender: 'pilot' | 'engineer';
  text: string;
  timestamp: number;
}

export interface AppConfig {
  vllmIp: string;
  micDevice: string;
  speakerDevice: string;
  pttHotkey: string;
  micSensitivity: number; // 0.0 to 1.0
}

interface AppState {
  // Red
  wsStatus: ConnectionStatus;
  latency: number;
  setWsStatus: (status: ConnectionStatus) => void;
  setLatency: (lat: number) => void;

  // Configuraciones
  config: AppConfig;
  updateConfig: (newConfig: Partial<AppConfig>) => void;

  // Radio y Diálogos
  radioMode: RadioMode;
  currentTranscript: string;
  radioHistory: RadioMessage[];
  keepQuiet: boolean;
  setRadioMode: (mode: RadioMode) => void;
  setCurrentTranscript: (text: string) => void;
  appendRadioMessage: (message: Omit<RadioMessage, 'id' | 'timestamp'>) => void;
  clearTranscript: () => void;
  setKeepQuiet: (enabled: boolean) => void;

  // Telemetría
  telemetry: TelemetryData | null;
  setTelemetry: (data: TelemetryData) => void;

  // Alertas Spotter
  activeAlerts: SpotterAlert[];
  triggerAlert: (alert: Omit<SpotterAlert, 'id' | 'timestamp'>) => void;
  dismissAlert: (id: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Conectividad
  wsStatus: 'DISCONNECTED',
  latency: 0,
  setWsStatus: (status) => set({ wsStatus: status }),
  setLatency: (lat) => set({ latency: lat }),

  // Configuraciones por defecto
  config: {
    vllmIp: 'hipfire',
    micDevice: 'default',
    speakerDevice: 'default',
    pttHotkey: 'Control',
    micSensitivity: 0.15,
  },
  updateConfig: (newConfig) =>
    set((state) => ({ config: { ...state.config, ...newConfig } })),

  // Radio y Diálogos
  radioMode: 'IDLE',
  currentTranscript: '',
  radioHistory: [],
  setRadioMode: (mode) => set({ radioMode: mode }),
  setCurrentTranscript: (text) => set({ currentTranscript: text }),
  appendRadioMessage: (msg) =>
    set((state) => ({
      radioHistory: [
        ...state.radioHistory,
        {
          ...msg,
          id: Math.random().toString(36).substr(2, 9),
          timestamp: Date.now(),
        },
      ],
    })),
  clearTranscript: () => set({ currentTranscript: '' }),
  keepQuiet: false,
  setKeepQuiet: (enabled) => set({ keepQuiet: enabled }),

  // Telemetría
  telemetry: null,
  setTelemetry: (data) => set({ telemetry: data }),

  // Alertas del Spotter
  activeAlerts: [],
  triggerAlert: (alert) =>
    set((state) => {
      const id = Math.random().toString(36).substr(2, 9);
      const newAlert: SpotterAlert = {
        ...alert,
        id,
        timestamp: Date.now(),
      };
      
      // Auto-remover alertas de baja severidad a los 5 segundos
      if (alert.severity !== 'critical') {
        setTimeout(() => {
          set((s) => ({
            activeAlerts: s.activeAlerts.filter((a) => a.id !== id),
          }));
        }, 5000);
      }

      return { activeAlerts: [newAlert, ...state.activeAlerts] };
    }),
  dismissAlert: (id) =>
    set((state) => ({
      activeAlerts: state.activeAlerts.filter((alert) => alert.id !== id),
    })),
}));
