import { describe, it, expect } from "vitest";
import {
  clampOverlaySpeakingHeight,
  OVERLAY_SPEAKING_DEFAULT_HEIGHT_PX,
  OVERLAY_SPEAKING_MAX_HEIGHT_PX,
  OVERLAY_SPEAKING_MIN_HEIGHT_PX,
} from "../overlay/overlayDimensions";

describe("overlayDimensions", () => {
  it("clamps speaking height between min and max", () => {
    expect(clampOverlaySpeakingHeight(50)).toBe(OVERLAY_SPEAKING_MIN_HEIGHT_PX);
    expect(clampOverlaySpeakingHeight(180)).toBe(180);
    expect(clampOverlaySpeakingHeight(999)).toBe(OVERLAY_SPEAKING_MAX_HEIGHT_PX);
  });

  it("falls back to default for invalid height", () => {
    expect(clampOverlaySpeakingHeight(NaN)).toBe(OVERLAY_SPEAKING_DEFAULT_HEIGHT_PX);
  });
});
