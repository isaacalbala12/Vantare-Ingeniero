import { beforeEach, describe, expect, it } from "vitest";
import {
  handleBackendVoicePlaybackEnd,
  handleBackendVoicePlaybackStart,
  resetBackendVoiceOverlayState,
} from "../services/backendVoiceOverlay";
import { useAppStore } from "../store/config";

describe("backendVoiceOverlay", () => {
  beforeEach(() => {
    resetBackendVoiceOverlayState();
    useAppStore.setState({
      config: { ...useAppStore.getState().config, voiceBackendPlayback: true },
      radio: {
        ...useAppStore.getState().radio,
        mode: "IDLE",
        voicePlaybackText: "",
      },
    });
  });

  it("shows speaking overlay on voice_playback_start", () => {
    handleBackendVoicePlaybackStart({
      playback_id: "p1",
      text: "Coche a la derecha",
      category: "proximity",
    });
    const state = useAppStore.getState();
    expect(state.radio.mode).toBe("SPEAKING_ENGINE");
    expect(state.radio.voicePlaybackText).toBe("Coche a la derecha");
  });

  it("hides overlay on matching voice_playback_end", () => {
    handleBackendVoicePlaybackStart({ playback_id: "p1", text: "Alerta" });
    handleBackendVoicePlaybackEnd({ playback_id: "p1" });
    const state = useAppStore.getState();
    expect(state.radio.mode).toBe("IDLE");
    expect(state.radio.voicePlaybackText).toBe("");
  });

  it("ignores events when voiceBackendPlayback is false", () => {
    useAppStore.setState({
      config: { ...useAppStore.getState().config, voiceBackendPlayback: false },
    });
    handleBackendVoicePlaybackStart({ playback_id: "p1", text: "Alerta" });
    expect(useAppStore.getState().radio.mode).toBe("IDLE");
  });

  it("ignores stale voice_playback_end", () => {
    handleBackendVoicePlaybackStart({ playback_id: "p1", text: "Uno" });
    handleBackendVoicePlaybackStart({ playback_id: "p2", text: "Dos" });
    handleBackendVoicePlaybackEnd({ playback_id: "p1" });
    const state = useAppStore.getState();
    expect(state.radio.mode).toBe("SPEAKING_ENGINE");
    expect(state.radio.voicePlaybackText).toBe("Dos");
  });
});
