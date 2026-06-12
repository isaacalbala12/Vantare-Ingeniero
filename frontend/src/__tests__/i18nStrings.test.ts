import { describe, expect, it } from "vitest";
import { STRINGS, t } from "../i18n/strings";

describe("i18n strings", () => {
  it("has the same keys in Spanish and English", () => {
    expect(Object.keys(STRINGS.en).sort()).toEqual(Object.keys(STRINGS.es).sort());
  });

  it("falls back to Spanish by default", () => {
    expect(t(undefined, "settings")).toBe(STRINGS.es.settings);
  });

  it("returns English when requested", () => {
    expect(t("en", "settings")).toBe(STRINGS.en.settings);
  });

  it("falls back to Spanish for unsupported language values", () => {
    expect(t("fr" as "es", "settings")).toBe(STRINGS.es.settings);
  });

  it("supports parameter substitution", () => {
    const result = t("en", "spotterAlert", { text: "car left" });
    expect(result).toBe("Spotter: car left");
  });
});
