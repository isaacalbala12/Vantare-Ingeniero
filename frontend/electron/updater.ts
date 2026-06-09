import { app, BrowserWindow } from "electron";
import { autoUpdater, type UpdateInfo } from "electron-updater";

export type DesktopUpdatePhase =
  | "idle"
  | "checking"
  | "available"
  | "not-available"
  | "downloading"
  | "downloaded"
  | "error";

export interface DesktopUpdateSnapshot {
  phase: DesktopUpdatePhase;
  currentVersion: string;
  latestVersion?: string;
  percent?: number;
  bytesPerSecond?: number;
  transferred?: number;
  total?: number;
  message?: string;
}

let snapshot: DesktopUpdateSnapshot = {
  phase: "idle",
  currentVersion: app.getVersion(),
};

function broadcast(win: BrowserWindow | null, next: DesktopUpdateSnapshot): void {
  snapshot = next;
  win?.webContents.send("desktop-update:status", snapshot);
}

export function getDesktopUpdateSnapshot(): DesktopUpdateSnapshot {
  return snapshot;
}

export function initDesktopUpdater(getHubWindow: () => BrowserWindow | null): void {
  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on("checking-for-update", () => {
    broadcast(getHubWindow(), { phase: "checking", currentVersion: app.getVersion() });
  });

  autoUpdater.on("update-available", (info: UpdateInfo) => {
    broadcast(getHubWindow(), {
      phase: "available",
      currentVersion: app.getVersion(),
      latestVersion: info.version,
    });
  });

  autoUpdater.on("update-not-available", () => {
    broadcast(getHubWindow(), {
      phase: "not-available",
      currentVersion: app.getVersion(),
    });
  });

  autoUpdater.on("download-progress", (progress) => {
    broadcast(getHubWindow(), {
      phase: "downloading",
      currentVersion: app.getVersion(),
      percent: progress.percent,
      bytesPerSecond: progress.bytesPerSecond,
      transferred: progress.transferred,
      total: progress.total,
    });
  });

  autoUpdater.on("update-downloaded", (info: UpdateInfo) => {
    broadcast(getHubWindow(), {
      phase: "downloaded",
      currentVersion: app.getVersion(),
      latestVersion: info.version,
    });
  });

  autoUpdater.on("error", (err: Error) => {
    broadcast(getHubWindow(), {
      phase: "error",
      currentVersion: app.getVersion(),
      message: err.message,
    });
  });
}

export function checkForDesktopUpdates(): Promise<DesktopUpdateSnapshot> {
  if (!app.isPackaged) {
    const dev: DesktopUpdateSnapshot = {
      phase: "error",
      currentVersion: app.getVersion(),
      message: "Actualizaciones solo disponibles en la app instalada",
    };
    snapshot = dev;
    return Promise.resolve(dev);
  }

  return new Promise((resolve) => {
    const settle = (next: DesktopUpdateSnapshot) => {
      snapshot = next;
      resolve(next);
    };

    const onAvailable = (info: UpdateInfo) => {
      cleanup();
      settle({
        phase: "available",
        currentVersion: app.getVersion(),
        latestVersion: info.version,
      });
    };

    const onNotAvailable = () => {
      cleanup();
      settle({
        phase: "not-available",
        currentVersion: app.getVersion(),
      });
    };

    const onError = (err: Error) => {
      cleanup();
      settle({
        phase: "error",
        currentVersion: app.getVersion(),
        message: err.message,
      });
    };

    const cleanup = () => {
      autoUpdater.removeListener("update-available", onAvailable);
      autoUpdater.removeListener("update-not-available", onNotAvailable);
      autoUpdater.removeListener("error", onError);
    };

    autoUpdater.once("update-available", onAvailable);
    autoUpdater.once("update-not-available", onNotAvailable);
    autoUpdater.once("error", onError);

    broadcast(null, { phase: "checking", currentVersion: app.getVersion() });
    void autoUpdater.checkForUpdates();
  });
}

export async function downloadDesktopUpdate(): Promise<void> {
  await autoUpdater.downloadUpdate();
}

export function quitAndInstallDesktopUpdate(): void {
  autoUpdater.quitAndInstall(false, true);
}
