import { describe, it, expect, vi, beforeEach } from "vitest";
import { createDesktopUpdateController } from "../services/desktopUpdate";

describe("desktopUpdate controller", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("maps not-available phase to user label", async () => {
    const check = vi.fn().mockResolvedValue({
      phase: "not-available",
      currentVersion: "0.1.0",
    });
    const ctrl = createDesktopUpdateController({
      check,
      download: vi.fn(),
      quitAndInstall: vi.fn(),
      getStatus: vi.fn(),
      subscribe: () => () => {},
    });
    const status = await ctrl.check();
    expect(ctrl.labelFor(status)).toBe("Estás en la última versión.");
  });

  it("maps available phase with version", async () => {
    const check = vi.fn().mockResolvedValue({
      phase: "available",
      currentVersion: "0.1.0",
      latestVersion: "0.2.0",
    });
    const ctrl = createDesktopUpdateController({
      check,
      download: vi.fn(),
      quitAndInstall: vi.fn(),
      getStatus: vi.fn(),
      subscribe: () => () => {},
    });
    const status = await ctrl.check();
    expect(ctrl.labelFor(status)).toBe("Versión 0.2.0 disponible.");
  });
});
