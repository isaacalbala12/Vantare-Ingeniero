import { describe, it, expect, beforeEach } from "vitest";

describe("AppStore (appStore.ts)", () => {
  beforeEach(() => {
    // Limpiar módulo para estado fresco
    vi.resetModules();
  });

  it("debe tener estado inicial correcto", async () => {
    const { useAppStore } = await import("../store/appStore");
    const state = useAppStore.getState();
    expect(state.wsStatus).toBe("DISCONNECTED");
    expect(state.latency).toBe(0);
    expect(state.radioMode).toBe("IDLE");
    expect(state.currentTranscript).toBe("");
    expect(state.radioHistory).toEqual([]);
    expect(state.telemetry).toBeNull();
    expect(state.activeAlerts).toEqual([]);
    expect(state.config.vllmIp).toBe("hipfire");
    expect(state.config.micSensitivity).toBe(0.15);
  });

  it("setWsStatus debe actualizar estado conexión", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().setWsStatus("CONNECTED");
    expect(useAppStore.getState().wsStatus).toBe("CONNECTED");
  });

  it("setWsStatus DISCONNECTED debe funcionar", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().setWsStatus("DISCONNECTED");
    expect(useAppStore.getState().wsStatus).toBe("DISCONNECTED");
  });

  it("setLatency debe actualizar latencia", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().setLatency(42);
    expect(useAppStore.getState().latency).toBe(42);
  });

  it("updateConfig debe fusionar configuración", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().updateConfig({ vllmIp: "127.0.0.1" });
    const config = useAppStore.getState().config;
    expect(config.vllmIp).toBe("127.0.0.1");
    expect(config.micDevice).toBe("default"); // Preservado
  });

  it("updateConfig debe preservar campos no actualizados", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().updateConfig({ micSensitivity: 0.5 });
    expect(useAppStore.getState().config.micSensitivity).toBe(0.5);
    expect(useAppStore.getState().config.vllmIp).toBe("hipfire");
  });

  it("setRadioMode debe actualizar modo radio", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().setRadioMode("THINKING_LLM");
    expect(useAppStore.getState().radioMode).toBe("THINKING_LLM");
  });

  it("setRadioMode debe aceptar SPEAKING_ENGINE", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().setRadioMode("SPEAKING_ENGINE");
    expect(useAppStore.getState().radioMode).toBe("SPEAKING_ENGINE");
  });

  it("setCurrentTranscript debe actualizar transcripción", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().setCurrentTranscript("¿Cómo va mi ritmo?");
    expect(useAppStore.getState().currentTranscript).toBe("¿Cómo va mi ritmo?");
  });

  it("appendRadioMessage debe añadir mensaje al historial", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().appendRadioMessage({ sender: "pilot", text: "Hola" });
    const history = useAppStore.getState().radioHistory;
    expect(history.length).toBe(1);
    expect(history[0].sender).toBe("pilot");
    expect(history[0].text).toBe("Hola");
    expect(history[0].id).toBeDefined();
    expect(history[0].timestamp).toBeDefined();
  });

  it("appendRadioMessage debe añadir múltiples mensajes", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().appendRadioMessage({ sender: "pilot", text: "Pregunta" });
    useAppStore.getState().appendRadioMessage({ sender: "engineer", text: "Respuesta" });
    expect(useAppStore.getState().radioHistory.length).toBe(2);
  });

  it("clearTranscript debe limpiar transcripción", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().setCurrentTranscript("texto temporal");
    useAppStore.getState().clearTranscript();
    expect(useAppStore.getState().currentTranscript).toBe("");
  });

  it("setTelemetry debe actualizar datos de telemetría", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().setTelemetry({
      speed: 180,
      gear: 4,
      rpm: 8500,
      lapNumber: 5,
      fuelInTank: 42.0,
      estimatedLapsRemaining: 13,
      fuelNeededToFinish: 80,
      wearFL: 72,
      wearFR: 68,
      wearRL: 65,
      wearRR: 63,
      sessionTimeLeft: 3600,
      sessionLapsLeft: 30,
    });
    const telemetry = useAppStore.getState().telemetry;
    expect(telemetry).not.toBeNull();
    expect(telemetry!.speed).toBe(180);
    expect(telemetry!.lapNumber).toBe(5);
    expect(telemetry!.fuelInTank).toBe(42.0);
  });

  it("triggerAlert debe añadir alerta con id y timestamp", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().triggerAlert({
      type: "fuel_low",
      message: "Combustible bajo",
      severity: "high",
    });
    const alerts = useAppStore.getState().activeAlerts;
    expect(alerts.length).toBe(1);
    expect(alerts[0].type).toBe("fuel_low");
    expect(alerts[0].message).toBe("Combustible bajo");
    expect(alerts[0].severity).toBe("high");
    expect(alerts[0].id).toBeDefined();
    expect(alerts[0].timestamp).toBeDefined();
  });

  it("dismissAlert debe eliminar alerta por id", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().triggerAlert({
      type: "fuel_low",
      message: "Combustible bajo",
      severity: "high",
    });
    const alertId = useAppStore.getState().activeAlerts[0].id;
    useAppStore.getState().dismissAlert(alertId);
    expect(useAppStore.getState().activeAlerts.length).toBe(0);
  });

  it("dismissAlert con id inexistente no debe crashear", async () => {
    const { useAppStore } = await import("../store/appStore");
    useAppStore.getState().dismissAlert("id-inexistente");
    expect(useAppStore.getState().activeAlerts).toEqual([]);
  });
});
