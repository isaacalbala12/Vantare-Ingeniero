/**
 * Tests unitarios para el store Zustand (config.ts).
 *
 * Verifica:
 * - El store inicializa con valores por defecto.
 * - updateConfig() actualiza la configuración.
 * - setRadioMode() cambia el modo correctamente.
 * - La configuración se persiste en localStorage.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useAppStore } from "../store/config";

describe("AppStore", () => {
  // Resetear el store antes de cada test
  beforeEach(() => {
    useAppStore.setState({
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
      config: {
        vllmIP: "localhost",
        serverPort: 8008,
        micDevice: "default",
        speakerDevice: "default",
        wakeWord: "ingeniero",
        sensitivity: 50,
        pttHotkey: "Ctrl+Shift+P",
        pttStopHotkey: "Ctrl+Shift+P",
        wakeWordEnabled: true,
      },
    });
    localStorage.clear();
  });

  describe("Estado Inicial", () => {
    it("debe tener valores por defecto en connectivity", () => {
      const state = useAppStore.getState();
      expect(state.connectivity.wsStatus).toBe("DISCONNECTED");
      expect(state.connectivity.latency).toBe(0);
      expect(state.connectivity.backendHealth).toBeNull();
    });

    it("debe tener valores por defecto en radio", () => {
      const state = useAppStore.getState();
      expect(state.radio.mode).toBe("IDLE");
      expect(state.radio.currentTokens).toBe("");
      expect(state.radio.messageHistory).toEqual([]);
      expect(state.radio.micLevel).toBe(0);
    });

    it("debe tener valores por defecto en telemetry", () => {
      const state = useAppStore.getState();
      expect(state.telemetry.speed).toBe(0);
      expect(state.telemetry.fuel).toBe(0.0);
      expect(state.telemetry.lap).toBe(1);
      expect(state.telemetry.position).toBe(1);
    });

    it("debe tener configuración por defecto", () => {
      const state = useAppStore.getState();
      expect(state.config.vllmIP).toBe("localhost");
      expect(state.config.serverPort).toBe(8008);
      expect(state.config.pttHotkey).toBe("Ctrl+Shift+P");
      expect(state.config.sensitivity).toBe(50);
    });

    it("debe tener screen = dashboard por defecto", () => {
      const state = useAppStore.getState();
      expect(state.screen).toBe("dashboard");
    });
  });

  describe("updateConfig", () => {
    it("debe actualizar la IP del servidor", () => {
      useAppStore.getState().updateConfig({ vllmIP: "192.168.1.100" });
      expect(useAppStore.getState().config.vllmIP).toBe("192.168.1.100");
    });

    it("debe actualizar el puerto", () => {
      useAppStore.getState().updateConfig({ serverPort: 9090 });
      expect(useAppStore.getState().config.serverPort).toBe(9090);
    });

    it("debe actualizar el hotkey", () => {
      useAppStore.getState().updateConfig({ pttHotkey: "Ctrl+Space" });
      expect(useAppStore.getState().config.pttHotkey).toBe("Ctrl+Space");
    });

    it("debe actualizar la sensibilidad", () => {
      useAppStore.getState().updateConfig({ sensitivity: 75 });
      expect(useAppStore.getState().config.sensitivity).toBe(75);
    });

    it("debe persistir en localStorage", () => {
      useAppStore.getState().updateConfig({ vllmIP: "10.0.0.1", serverPort: 8000 });
      const saved = JSON.parse(localStorage.getItem("vantare_config") || "{}");
      expect(saved.vllmIP).toBe("10.0.0.1");
      expect(saved.serverPort).toBe(8000);
    });
  });

  describe("setRadioMode", () => {
    it("debe cambiar a LISTENING_PILOT", () => {
      useAppStore.getState().setRadioMode("LISTENING_PILOT");
      expect(useAppStore.getState().radio.mode).toBe("LISTENING_PILOT");
    });

    it("debe cambiar a THINKING_LLM", () => {
      useAppStore.getState().setRadioMode("THINKING_LLM");
      expect(useAppStore.getState().radio.mode).toBe("THINKING_LLM");
    });

    it("debe cambiar a SPEAKING_ENGINE", () => {
      useAppStore.getState().setRadioMode("SPEAKING_ENGINE");
      expect(useAppStore.getState().radio.mode).toBe("SPEAKING_ENGINE");
    });

    it("debe volver a IDLE", () => {
      useAppStore.getState().setRadioMode("LISTENING_PILOT");
      useAppStore.getState().setRadioMode("IDLE");
      expect(useAppStore.getState().radio.mode).toBe("IDLE");
    });
  });

  describe("setWsStatus", () => {
    it("debe cambiar el estado del WebSocket", () => {
      useAppStore.getState().setWsStatus("CONNECTED");
      expect(useAppStore.getState().connectivity.wsStatus).toBe("CONNECTED");

      useAppStore.getState().setWsStatus("DISCONNECTED");
      expect(useAppStore.getState().connectivity.wsStatus).toBe("DISCONNECTED");
    });
  });

  describe("setLatency", () => {
    it("debe actualizar la latencia", () => {
      useAppStore.getState().setLatency(42);
      expect(useAppStore.getState().connectivity.latency).toBe(42);
    });
  });

  describe("setBackendHealth", () => {
    it("debe actualizar el health del backend", () => {
      const health = {
        shared_memory: true,
        lmu_api: true,
        llm: true,
        websocket: true,
      };
      useAppStore.getState().setBackendHealth(health);
      expect(useAppStore.getState().connectivity.backendHealth).toEqual(health);
    });

    it("debe aceptar null", () => {
      useAppStore.getState().setBackendHealth(null);
      expect(useAppStore.getState().connectivity.backendHealth).toBeNull();
    });
  });

  describe("updateTelemetry", () => {
    it("debe actualizar la velocidad", () => {
      useAppStore.getState().updateTelemetry({ speed: 280 });
      expect(useAppStore.getState().telemetry.speed).toBe(280);
    });

    it("debe actualizar el combustible", () => {
      useAppStore.getState().updateTelemetry({ fuel: 45.5 });
      expect(useAppStore.getState().telemetry.fuel).toBe(45.5);
    });

    it("debe actualizar parcialmente sin perder otros campos", () => {
      useAppStore.getState().updateTelemetry({ speed: 300 });
      useAppStore.getState().updateTelemetry({ gear: 5 });
      const state = useAppStore.getState().telemetry;
      expect(state.speed).toBe(300);
      expect(state.gear).toBe(5);
      expect(state.fuel).toBe(0.0); // Valor por defecto
    });
  });

  describe("setScreen", () => {
    it("debe cambiar a config", () => {
      useAppStore.getState().setScreen("config");
      expect(useAppStore.getState().screen).toBe("config");
    });

    it("debe cambiar a dashboard", () => {
      useAppStore.getState().setScreen("config");
      useAppStore.getState().setScreen("dashboard");
      expect(useAppStore.getState().screen).toBe("dashboard");
    });
  });

  describe("addMessageToHistory", () => {
    it("debe añadir un mensaje del piloto", () => {
      useAppStore.getState().addMessageToHistory("pilot", "¿Cómo va el combustible?");
      const history = useAppStore.getState().radio.messageHistory;
      expect(history.length).toBe(1);
      expect(history[0].sender).toBe("pilot");
      expect(history[0].text).toBe("¿Cómo va el combustible?");
    });

    it("debe añadir un mensaje del ingeniero", () => {
      useAppStore.getState().addMessageToHistory("engineer", "Copiado piloto, todo en orden.");
      const history = useAppStore.getState().radio.messageHistory;
      expect(history.length).toBe(1);
      expect(history[0].sender).toBe("engineer");
    });

    it("debe acumular múltiples mensajes", () => {
      useAppStore.getState().addMessageToHistory("pilot", "Mensaje 1");
      useAppStore.getState().addMessageToHistory("engineer", "Respuesta 1");
      useAppStore.getState().addMessageToHistory("pilot", "Mensaje 2");
      expect(useAppStore.getState().radio.messageHistory.length).toBe(3);
    });
  });
});
