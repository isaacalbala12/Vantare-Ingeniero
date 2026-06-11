import { describe, expect, it } from "vitest";
import {
  flattenAlertPayload,
  shouldVoiceAlert,
  shouldVoiceDuringSpeakOnly,
  shouldVoiceForServiceToggle,
} from "../services/alertVoice";
import { evaluateAlertTts } from "../services/ttsPlaybackGate";

/** Réplica la lógica de historial vs TTS en useWebSocket alert handler. */
function simulateAlertPaths(params: {
  message: string;
  payload: Record<string, unknown>;
  voiceBackendPlayback: boolean;
}) {
  const category = String(params.payload.category || "").toLowerCase();
  const voicePayload = flattenAlertPayload(params.payload);
  const shouldLogRadioHistory =
    Boolean(params.message) &&
    shouldVoiceAlert(voicePayload) &&
    shouldVoiceDuringSpeakOnly(false, category, "alert") &&
    shouldVoiceForServiceToggle(category, true, true, voicePayload);
  const ttsDecision = evaluateAlertTts({
    message: params.message,
    payload: params.payload,
    speakOnlyWhenSpokenTo: false,
    spotterEnabled: true,
    engineerEnabled: true,
    voiceBackendPlayback: params.voiceBackendPlayback,
  });
  return { shouldLogRadioHistory, ttsDecision };
}

describe("useWebSocket alert paths with voiceBackendPlayback", () => {
  it("backend playback: historial sí, TTS frontend no", () => {
    const payload = {
      category: "proximity",
      severity: "INFO",
      audio_priority: "2",
      message: "Coche a la derecha",
    };
    const { shouldLogRadioHistory, ttsDecision } = simulateAlertPaths({
      message: "Coche a la derecha",
      payload,
      voiceBackendPlayback: true,
    });
    expect(shouldLogRadioHistory).toBe(true);
    expect(ttsDecision.allow).toBe(false);
    expect(ttsDecision.reason).toBe("backend_playback");
  });

  it("frontend playback: historial y TTS permitidos", () => {
    const payload = {
      category: "proximity",
      severity: "INFO",
      audio_priority: "2",
      message: "Coche a la derecha",
    };
    const { shouldLogRadioHistory, ttsDecision } = simulateAlertPaths({
      message: "Coche a la derecha",
      payload,
      voiceBackendPlayback: false,
    });
    expect(shouldLogRadioHistory).toBe(true);
    expect(ttsDecision.allow).toBe(true);
  });
});
