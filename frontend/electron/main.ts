import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { app, BrowserWindow, ipcMain, Menu, Tray } from "electron";
import { createHubWindow } from "./windows/hubWindow";
import {
  getOverlayWindow,
  hideOverlayWindow,
  resizeOverlayContent,
  setOverlayPresentation,
  showOverlayWindow,
  toggleOverlayWindow,
  type OverlayPresentation,
} from "./windows/overlayWindow";
import { registerPttShortcuts, unregisterPttShortcuts } from "./shortcuts/ptt";
import { registerGamepadIpc } from "./shortcuts/gamepadPoll";
import { openExternalUrl } from "./security/urls";
import { resolveHistoryFile } from "./security/historyFiles";
import {
  checkForDesktopUpdates,
  downloadDesktopUpdate,
  getDesktopUpdateSnapshot,
  initDesktopUpdater,
  quitAndInstallDesktopUpdate,
} from "./updater";

const isDev = !app.isPackaged;
let hubWindow: BrowserWindow | null = null;
let backendChild: ChildProcessWithoutNullStreams | null = null;
let tray: Tray | null = null;
/** null = unchecked, true/false = cached availability */
let duckLmuAvailable: boolean | null = null;

/** Evita crash EPIPE cuando stdout/stderr no tienen pipe (p. ej. Electron empaquetado). */
function ignorePipeErrors(stream: NodeJS.WriteStream | null | undefined): void {
  stream?.on("error", (err: NodeJS.ErrnoException) => {
    if (err.code !== "EPIPE") throw err;
  });
}

ignorePipeErrors(process.stdout);
ignorePipeErrors(process.stderr);

function historyDir(): string {
  return path.join(app.getPath("userData"), "history");
}

async function duckLmu(active: boolean, level: number): Promise<void> {
  if (duckLmuAvailable === false) return;

  const exeName = process.platform === "win32" ? "duck_lmu.exe" : "duck_lmu";
  const exePath = isDev
    ? path.join(__dirname, "..", "..", "native", "duck_lmu", "target", "release", exeName)
    : path.join(process.resourcesPath, exeName);

  if (duckLmuAvailable === null) {
    try {
      await fs.access(exePath);
      duckLmuAvailable = true;
    } catch {
      duckLmuAvailable = false;
      return;
    }
  }

  spawn(exePath, ["--active", String(active), "--level", String(level)], {
    stdio: "ignore",
    windowsHide: true,
  }).unref();
}

function spawnBackendIfRelease(): void {
  if (isDev) {
    console.log("[electron] dev mode: backend not auto-spawned");
    return;
  }

  const backendPath = path.join(process.resourcesPath, "backend", "backend.exe");
  backendChild = spawn(backendPath, [], {
    env: { ...process.env, PORT: "8008", VANTARE_NATIVE_TELEMETRY: "1" },
    stdio: "pipe",
    windowsHide: true,
  });

  backendChild.stdout?.on("data", (chunk: Buffer) => {
    console.log("[backend]", chunk.toString().trim());
  });
  backendChild.stderr?.on("data", (chunk: Buffer) => {
    console.error("[backend]", chunk.toString().trim());
  });
}

function registerIpc(): void {
  registerGamepadIpc();

  ipcMain.handle("shell:openExternal", (_event, url: string) => openExternalUrl(url));

  ipcMain.handle("audio:duckLmu", (_event, args: { active: boolean; level?: number }) => {
    return duckLmu(args.active, args.level ?? 0.65);
  });

  ipcMain.handle("overlay:toggle", () => toggleOverlayWindow(isDev));
  ipcMain.handle("overlay:show", () => showOverlayWindow(isDev));
  ipcMain.handle("overlay:hide", () => hideOverlayWindow());
  ipcMain.handle("overlay:setPresentation", (_event, presentation: OverlayPresentation) =>
    setOverlayPresentation(presentation, isDev),
  );

  ipcMain.on("overlay:resizeContent", (_event, size: { width?: number; height?: number }) => {
    if (!size || typeof size.width !== "number" || typeof size.height !== "number") return;
    resizeOverlayContent(size.width, size.height);
  });

  ipcMain.handle("overlay:setResizeMode", (_event, enabled: boolean) => {
    const overlay = getOverlayWindow();
    if (!overlay) return;
    overlay.setResizable(enabled);
  });

  ipcMain.handle("ptt:updateHotkeys", (_event, payload: { start: string; stop: string }) => {
    return registerPttShortcuts(hubWindow, payload);
  });

  ipcMain.handle("history:save", async (_event, payload: unknown) => {
    const dir = historyDir();
    await fs.mkdir(dir, { recursive: true });
    const data = payload as { sessionId: string; startedAt: string };
    const stamp = data.startedAt.slice(0, 10).replace(/-/g, "");
    const filename = `${stamp}-${data.sessionId}.json`;
    await fs.writeFile(path.join(dir, filename), JSON.stringify(payload, null, 2), "utf8");
    return filename;
  });

  ipcMain.handle("history:list", async () => {
    const dir = historyDir();
    try {
      const files = await fs.readdir(dir);
      return files.filter((f) => f.endsWith(".json")).sort().reverse();
    } catch {
      return [];
    }
  });

  ipcMain.handle("history:load", async (_event, filename: string) => {
    const filePath = resolveHistoryFile(historyDir(), filename);
    const raw = await fs.readFile(filePath, "utf8");
    return JSON.parse(raw);
  });

  ipcMain.handle("desktop-update:getStatus", () => getDesktopUpdateSnapshot());
  ipcMain.handle("desktop-update:check", () => checkForDesktopUpdates());
  ipcMain.handle("desktop-update:download", () => downloadDesktopUpdate());
  ipcMain.handle("desktop-update:quitAndInstall", () => quitAndInstallDesktopUpdate());
}

function resolveTrayIcon(): string {
  const packaged = path.join(process.resourcesPath, "icons", "icon.ico");
  const dev = path.join(__dirname, "../src-tauri/icons/icon.ico");
  return isDev ? dev : packaged;
}

function createTray(): void {
  tray = new Tray(resolveTrayIcon());
  const menu = Menu.buildFromTemplate([
    { label: "Mostrar Hub", click: () => hubWindow?.show() },
    { type: "separator" },
    { label: "Salir", click: () => app.quit() },
  ]);
  tray.setToolTip("Vantare Ingeniero");
  tray.setContextMenu(menu);
}

app.whenReady().then(async () => {
  registerIpc();
  initDesktopUpdater(() => hubWindow);
  spawnBackendIfRelease();
  hubWindow = createHubWindow(isDev);
  createTray();
  await registerPttShortcuts(hubWindow);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      hubWindow = createHubWindow(isDev);
      void registerPttShortcuts(hubWindow);
    }
  });
});

app.on("will-quit", () => {
  unregisterPttShortcuts();
  if (backendChild && !backendChild.killed) {
    backendChild.kill();
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
