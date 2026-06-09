import { describe, it, expect, beforeEach, vi } from "vitest";
import { getPlatform } from "../core/platform";

describe("getPlatform", () => {
  beforeEach(() => {
    delete (window as any).vantare;
  });

  it("returns web stub when bridge missing", () => {
    const platform = getPlatform();
    expect(platform.isElectron).toBe(false);
    expect(platform.isTauri).toBe(false);
  });

  it("uses electron bridge when present", async () => {
    const duckLmu = vi.fn();
    (window as any).vantare = {
      isElectron: true,
      duckLmu,
      openExternal: vi.fn(),
      saveSessionHistory: vi.fn(),
      listSessionHistories: vi.fn(),
      loadSessionHistory: vi.fn(),
      setOverlayResizeMode: vi.fn(),
      toggleOverlay: vi.fn(),
      showOverlay: vi.fn(),
      hideOverlay: vi.fn(),
    };
    const platform = getPlatform();
    expect(platform.isElectron).toBe(true);
    await platform.duckLmu(true, 0.5);
    expect(duckLmu).toHaveBeenCalledWith(true, 0.5);
  });
});
