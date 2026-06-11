import { describe, it, expect } from "vitest";
import { buildConfigUpdatePayload } from "../services/configUpdatePayload";

describe("personality config payload", () => {
  it("includes proactivityLevel and pearlFrequency", () => {
    const p = buildConfigUpdatePayload({
      proactivityLevel: "low",
      pearlFrequency: 0.3,
    } as any);
    expect(p.proactivityLevel).toBe("low");
    expect(p.pearlFrequency).toBe(0.3);
  });

  it("defaults proactivityLevel to normal", () => {
    const p = buildConfigUpdatePayload({} as any);
    expect(p.proactivityLevel).toBe("normal");
  });

  it("defaults pearlFrequency to 0.5", () => {
    const p = buildConfigUpdatePayload({} as any);
    expect(p.pearlFrequency).toBe(0.5);
  });
});
