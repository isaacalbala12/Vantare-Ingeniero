import { describe, it, expect, beforeEach } from "vitest";
import { useAppStore } from "../store/config";

describe("language config", () => {
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
        vllmIP: "127.0.0.1",
        serverPort: 8008,
        micDevice: "default",
        speakerDevice: "default",
        wakeWord: "ingeniero",
        sensitivity: 50,
        pttHotkey: "Ctrl+Shift+P",
        pttStopHotkey: "Ctrl+Shift+P",
        wakeWordEnabled: false,
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
        ttsProviderEngineer: "edge",
        ttsProviderSpotter: "edge",
        spotterClearDelayS: 0.15,
        spotterOverlapDelayS: 2.0,
        spotterHoldRepeatS: 3.0,
        spotterGapFrequencyS: 30,
        spotterCarLengthM: 4.5,
        spotterMinSpeedMs: 5.0,
        spotterRaceStartDelayS: 3.0,
        brakingZonesMute: false,
        speakOnlyWhenSpokenTo: true,
        ttsVolumeBoost: 100,
        spotterEnabled: true,
        engineerEnabled: false,
        voiceBackendPlayback: true,
        proactivityLevel: "normal",
        pearlFrequency: 0.5,
        uiLanguage: "es",
        voiceLanguage: "es",
      },
    });
    localStorage.clear();
  });

  it("defaults uiLanguage to es", () => {
    const state = useAppStore.getState();
    expect(state.config.uiLanguage).toBe("es");
  });

  it("defaults voiceLanguage to es", () => {
    const state = useAppStore.getState();
    expect(state.config.voiceLanguage).toBe("es");
  });

  it("allows setting uiLanguage to en", () => {
    useAppStore.getState().updateConfig({ uiLanguage: "en" });
    expect(useAppStore.getState().config.uiLanguage).toBe("en");
  });

  it("allows setting voiceLanguage to en", () => {
    useAppStore.getState().updateConfig({ voiceLanguage: "en" });
    expect(useAppStore.getState().config.voiceLanguage).toBe("en");
  });

  it("persists language fields to localStorage", () => {
    useAppStore.getState().updateConfig({ uiLanguage: "en", voiceLanguage: "en" });
    const saved = JSON.parse(localStorage.getItem("vantare_config") || "{}");
    expect(saved.uiLanguage).toBe("en");
    expect(saved.voiceLanguage).toBe("en");
  });

  it("normalizes invalid language values before saving", () => {
    useAppStore.getState().updateConfig({
      uiLanguage: "fr" as "es",
      voiceLanguage: "de" as "es",
    });
    const state = useAppStore.getState();
    const saved = JSON.parse(localStorage.getItem("vantare_config") || "{}");
    expect(state.config.uiLanguage).toBe("es");
    expect(state.config.voiceLanguage).toBe("es");
    expect(saved.uiLanguage).toBe("es");
    expect(saved.voiceLanguage).toBe("es");
  });
});
