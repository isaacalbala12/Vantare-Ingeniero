import { describe, expect, it } from "vitest";
import { buildConfigUpdatePayload } from "../services/configUpdatePayload";

describe("ttsProvider config", () => {
  it("includes provider fields in WS payload", () => {
    const p = buildConfigUpdatePayload({
      ttsProviderEngineer: "gemini",
      ttsProviderSpotter: "edge",
    } as any);
    expect(p.ttsProviderEngineer).toBe("gemini");
    expect(p.ttsProviderSpotter).toBe("edge");
  });
});
