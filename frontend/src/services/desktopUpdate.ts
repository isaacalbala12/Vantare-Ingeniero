import { useCallback, useEffect, useState } from "react";
import { getPlatform } from "../core/platform";
import type { DesktopUpdateStatus } from "../core/platform/types";

export interface DesktopUpdateDeps {
  getStatus: () => Promise<DesktopUpdateStatus>;
  check: () => Promise<DesktopUpdateStatus>;
  download: () => Promise<void>;
  quitAndInstall: () => Promise<void>;
  subscribe: (handler: (status: DesktopUpdateStatus) => void) => () => void;
}

export const RELEASE_PAGE_URL =
  "https://github.com/isaacalbala12/Vantare-Ingeniero/releases/latest";

export function labelForStatus(status: DesktopUpdateStatus): string {
  switch (status.phase) {
    case "idle":
      return "Comprueba si hay una versión nueva.";
    case "checking":
      return "Buscando actualizaciones…";
    case "available":
      return status.latestVersion
        ? `Versión ${status.latestVersion} disponible.`
        : "Actualización disponible.";
    case "not-available":
      return "Estás en la última versión.";
    case "downloading":
      return status.percent != null
        ? `Descargando… ${Math.round(status.percent)}%`
        : "Descargando actualización…";
    case "downloaded":
      return status.latestVersion
        ? `Listo para instalar v${status.latestVersion}. Reinicia la app.`
        : "Listo para instalar. Reinicia la app.";
    case "error":
      return status.message ?? "No se pudo comprobar actualizaciones.";
    default:
      return "";
  }
}

export function createDesktopUpdateController(deps: DesktopUpdateDeps) {
  return {
    check: deps.check,
    labelFor: labelForStatus,
  };
}

export function isDesktopUpdaterAvailable(): boolean {
  return typeof getPlatform().checkDesktopUpdates === "function";
}

export function useDesktopUpdate() {
  const platform = getPlatform();
  const desktopAvailable = isDesktopUpdaterAvailable();
  const [status, setStatus] = useState<DesktopUpdateStatus>({
    phase: "idle",
    currentVersion: "0.0.0",
  });

  useEffect(() => {
    if (!desktopAvailable || !platform.getDesktopUpdateStatus || !platform.subscribeDesktopUpdate) {
      return;
    }
    void platform.getDesktopUpdateStatus().then(setStatus);
    return platform.subscribeDesktopUpdate(setStatus);
  }, [desktopAvailable, platform]);

  const check = useCallback(async () => {
    if (!platform.checkDesktopUpdates) {
      return status;
    }
    const next = await platform.checkDesktopUpdates();
    setStatus(next);
    return next;
  }, [platform, status]);

  const download = useCallback(async () => {
    await platform.downloadDesktopUpdate?.();
  }, [platform]);

  const quitAndInstall = useCallback(async () => {
    await platform.quitAndInstallDesktopUpdate?.();
  }, [platform]);

  return {
    status,
    desktopAvailable,
    check,
    download,
    quitAndInstall,
    labelFor: labelForStatus,
  };
}
