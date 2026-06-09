import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  createDesktopUpdateController,
  runDesktopUpdateNow,
  waitForDesktopUpdatePhase,
} from "../services/desktopUpdate";
import type { DesktopUpdateStatus } from "../core/platform/types";

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

describe("runDesktopUpdateNow", () => {
  it("no hace nada si ya está al día", async () => {
    const download = vi.fn();
    const quitAndInstall = vi.fn();
    const result = await runDesktopUpdateNow({
      check: vi.fn().mockResolvedValue({ phase: "not-available", currentVersion: "0.2.0" }),
      download,
      quitAndInstall,
      getStatus: vi.fn(),
      subscribe: () => () => {},
    });
    expect(result.phase).toBe("not-available");
    expect(download).not.toHaveBeenCalled();
    expect(quitAndInstall).not.toHaveBeenCalled();
  });

  it("descarga e instala cuando hay update disponible", async () => {
    const download = vi.fn().mockResolvedValue(undefined);
    const quitAndInstall = vi.fn().mockResolvedValue(undefined);
    let handler: ((s: DesktopUpdateStatus) => void) | null = null;

    const result = await runDesktopUpdateNow({
      check: vi.fn().mockResolvedValue({
        phase: "available",
        currentVersion: "0.2.0",
        latestVersion: "0.2.1",
      }),
      download,
      quitAndInstall,
      getStatus: vi.fn(),
      subscribe: (cb) => {
        handler = cb;
        queueMicrotask(() => {
          handler?.({
            phase: "downloaded",
            currentVersion: "0.2.0",
            latestVersion: "0.2.1",
          });
        });
        return () => {
          handler = null;
        };
      },
    });

    expect(download).toHaveBeenCalledOnce();
    expect(quitAndInstall).toHaveBeenCalledOnce();
    expect(result.phase).toBe("downloaded");
  });

  it("waitForDesktopUpdatePhase rechaza en error", async () => {
    let handler: ((s: DesktopUpdateStatus) => void) | null = null;
    const promise = waitForDesktopUpdatePhase((cb) => {
      handler = cb;
      queueMicrotask(() => {
        handler?.({ phase: "error", currentVersion: "0.1.0", message: "fallo red" });
      });
      return () => {
        handler = null;
      };
    }, "downloaded");

    await expect(promise).rejects.toThrow("fallo red");
  });
});
