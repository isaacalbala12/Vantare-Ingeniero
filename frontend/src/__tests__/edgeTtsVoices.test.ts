import { describe, it, expect } from "vitest";
import { EDGE_TTS_VOICES_ES, voiceLabel, isKnownEdgeVoice } from "../hub/forms/edgeTtsVoices";

describe("edgeTtsVoices", () => {
  it("expone dos voces ES con labels humanos", () => {
    expect(EDGE_TTS_VOICES_ES).toHaveLength(2);
    expect(voiceLabel("es-ES-AlvaroNeural")).toBe("Hombre — Español");
    expect(voiceLabel("es-ES-ElviraNeural")).toBe("Mujer — Español");
  });

  it("isKnownEdgeVoice valida ids", () => {
    expect(isKnownEdgeVoice("es-ES-AlvaroNeural")).toBe(true);
    expect(isKnownEdgeVoice("en-US-JennyNeural")).toBe(false);
  });
});
