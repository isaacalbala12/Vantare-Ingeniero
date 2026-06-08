import { describe, it, expect, beforeEach } from "vitest";
import { getOverlayVariant } from "../overlay/variants/registry";

describe("getOverlayVariant", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("defaults to a1", () => {
    expect(getOverlayVariant()).toBe("a1");
  });

  it("reads a2 from localStorage", () => {
    localStorage.setItem("overlayVariant", "a2");
    expect(getOverlayVariant()).toBe("a2");
  });
});
