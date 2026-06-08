import { describe, it, expect } from "vitest";
import { radioModeToOverlayPresentation } from "../overlay/overlayPresentation";

describe("radioModeToOverlayPresentation", () => {
  it("hides overlay when idle", () => {
    expect(radioModeToOverlayPresentation("IDLE")).toBe("hidden");
  });

  it("shows listening chip during PTT", () => {
    expect(radioModeToOverlayPresentation("LISTENING_PILOT")).toBe("listening");
  });

  it("shows speaking card when engineer talks", () => {
    expect(radioModeToOverlayPresentation("SPEAKING_ENGINE")).toBe("speaking");
  });

  it("hides overlay while thinking", () => {
    expect(radioModeToOverlayPresentation("THINKING_LLM")).toBe("hidden");
  });
});
