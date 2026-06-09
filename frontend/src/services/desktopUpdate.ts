import { useCallback, useEffect, useRef, useState } from "react";
import { getPlatform } from "../core/platform";
import type { DesktopUpdatePhase, DesktopUpdateStatus } from "../core/platform/types";

/** Retraso antes del primer check silencioso al abrir la app (ms). */
export const DESKTOP_UPDATE_STARTUP_DELAY_MS = 8_000;

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
      return "Se buscarán actualizaciones al abrir la app.";
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

export function waitForDesktopUpdatePhase(
  subscribe: DesktopUpdateDeps["subscribe"],
  target: DesktopUpdatePhase | DesktopUpdatePhase[],
  timeoutMs = 600_000,
): Promise<DesktopUpdateStatus> {
  const targets = new Set(Array.isArray(target) ? target : [target]);

  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      unsub();
      fn();
    };

    const timer = window.setTimeout(() => {
      finish(() => reject(new Error("Tiempo de espera agotado al descargar la actualización")));
    }, timeoutMs);

    const unsub = subscribe((status) => {
      if (status.phase === "error") {
        finish(() => reject(new Error(status.message ?? "Error de actualización")));
        return;
      }
      if (targets.has(status.phase)) {
        finish(() => resolve(status));
      }
    });
  });
}

/** Check → descarga → reinicia e instala (un solo flujo para el usuario). */
export async function runDesktopUpdateNow(deps: DesktopUpdateDeps): Promise<DesktopUpdateStatus> {
  let status = await deps.check();

  if (status.phase === "not-available" || status.phase === "error") {
    return status;
  }

  if (status.phase === "downloaded") {
    await deps.quitAndInstall();
    return status;
  }

  if (status.phase === "available") {
    await deps.download();
    status = await waitForDesktopUpdatePhase(deps.subscribe, "downloaded");
    await deps.quitAndInstall();
    return status;
  }

  return status;
}

export function isDesktopUpdaterAvailable(): boolean {
  return typeof getPlatform().checkDesktopUpdates === "function";
}

export interface UseDesktopUpdateOptions {
  /** Comprueba updates automáticamente al montar (solo app empaquetada). */
  autoCheckOnMount?: boolean;
  /** Tras detectar update, descarga e instala sin interacción del usuario. */
  autoInstallWhenAvailable?: boolean;
  startupDelayMs?: number;
}

export function useDesktopUpdate(options: UseDesktopUpdateOptions = {}) {
  const {
    autoCheckOnMount = false,
    autoInstallWhenAvailable = false,
    startupDelayMs = DESKTOP_UPDATE_STARTUP_DELAY_MS,
  } = options;
  const platform = getPlatform();
  const desktopAvailable = isDesktopUpdaterAvailable();
  const startupCheckedRef = useRef(false);
  const autoInstallStartedRef = useRef(false);
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

  const deps = useCallback(
    (): DesktopUpdateDeps | null => {
      if (
        !platform.checkDesktopUpdates ||
        !platform.downloadDesktopUpdate ||
        !platform.quitAndInstallDesktopUpdate ||
        !platform.subscribeDesktopUpdate
      ) {
        return null;
      }
      return {
        getStatus: platform.getDesktopUpdateStatus!,
        check: platform.checkDesktopUpdates,
        download: platform.downloadDesktopUpdate,
        quitAndInstall: platform.quitAndInstallDesktopUpdate,
        subscribe: platform.subscribeDesktopUpdate,
      };
    },
    [platform],
  );

  const check = useCallback(async () => {
    const d = deps();
    if (!d) {
      return status;
    }
    const next = await d.check();
    setStatus(next);
    return next;
  }, [deps, status]);

  const download = useCallback(async () => {
    await platform.downloadDesktopUpdate?.();
  }, [platform]);

  const quitAndInstall = useCallback(async () => {
    await platform.quitAndInstallDesktopUpdate?.();
  }, [platform]);

  const updateNow = useCallback(async () => {
    const d = deps();
    if (!d) {
      return status;
    }
    try {
      const next = await runDesktopUpdateNow(d);
      setStatus(next);
      return next;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error de actualización";
      const failed: DesktopUpdateStatus = {
        phase: "error",
        currentVersion: status.currentVersion,
        message,
      };
      setStatus(failed);
      return failed;
    }
  }, [deps, status]);

  useEffect(() => {
    if (!autoCheckOnMount || !desktopAvailable || startupCheckedRef.current) {
      return;
    }
    startupCheckedRef.current = true;
    const timer = window.setTimeout(() => {
      void check();
    }, startupDelayMs);
    return () => clearTimeout(timer);
  }, [autoCheckOnMount, desktopAvailable, check, startupDelayMs]);

  useEffect(() => {
    if (!autoInstallWhenAvailable || !desktopAvailable) {
      return;
    }
    if (status.phase !== "available" || autoInstallStartedRef.current) {
      return;
    }
    autoInstallStartedRef.current = true;
    void updateNow();
  }, [autoInstallWhenAvailable, desktopAvailable, status.phase, updateNow]);

  return {
    status,
    desktopAvailable,
    check,
    download,
    quitAndInstall,
    updateNow,
    labelFor: labelForStatus,
  };
}
