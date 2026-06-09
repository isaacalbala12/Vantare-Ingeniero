import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { appendFileSync, existsSync } from "node:fs";
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

function appendBackendLog(line: string): void {
  try {
    const logPath = path.join(app.getPath("userData"), "backend.log");
    appendFileSync(logPath, `[${new Date().toISOString()}] ${line}\n`, "utf8");
  } catch {
    // ignore logging failures
  }
}

const BACKEND_HEALTH_URL = "http://127.0.0.1:8008/health";

async function waitForBackendReady(maxWaitMs = 120_000): Promise<boolean> {
  const deadline = Date.now() + maxWaitMs;
  while (Date.now() < deadline) {
    if (backendChild?.exitCode !== null && backendChild?.exitCode !== undefined) {
      appendBackendLog(`Backend exited during startup wait (code=${backendChild.exitCode})`);
      return false;
    }
    try {
      const res = await fetch(BACKEND_HEALTH_URL, { signal: AbortSignal.timeout(2_000) });
      if (res.ok) {
        const body = (await res.json()) as { status?: string };
        if (body.status === "ok") {
          appendBackendLog("Backend health OK");
          return true;
        }
      }
    } catch {
      // backend still starting
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }
  appendBackendLog("Backend health timeout");
  return false;
}

function spawnBackendIfRelease(): void {
  if (isDev) {
    console.log("[electron] dev mode: backend not auto-spawned");
    return;
  }

  const backendDir = path.join(process.resourcesPath, "backend");
  const backendPath = path.join(backendDir, "backend.exe");

  if (!existsSync(backendPath)) {
    const msg = `Backend no encontrado: ${backendPath}`;
    console.error("[electron]", msg);
    appendBackendLog(`ERROR ${msg}`);
    return;
  }

  appendBackendLog(`Spawning ${backendPath}`);

  backendChild = spawn(backendPath, [], {
    cwd: backendDir,
    env: {
      ...process.env,
      HOST: "127.0.0.1",
      PORT: "8008",
      VANTARE_NATIVE_TELEMETRY: "1",
    },
    stdio: "pipe",
    windowsHide: true,
  });

  backendChild.on("error", (err) => {
    const msg = `Backend spawn error: ${err.message}`;
    console.error("[electron]", msg);
    appendBackendLog(`ERROR ${msg}`);
  });

  backendChild.on("exit", (code, signal) => {
    const msg = `Backend exited code=${code ?? "null"} signal=${signal ?? "null"}`;
    console.error("[electron]", msg);
    appendBackendLog(msg);
  });

  backendChild.stdout?.on("data", (chunk: Buffer) => {
    const line = chunk.toString().trim();
    console.log("[backend]", line);
    appendBackendLog(`stdout ${line}`);
  });
  backendChild.stderr?.on("data", (chunk: Buffer) => {
    const line = chunk.toString().trim();
    console.error("[backend]", line);
    appendBackendLog(`stderr ${line}`);
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
  if (!isDev) {
    const ready = await waitForBackendReady();
    if (!ready) {
      console.error("[electron] Backend no respondió a /health — revisa backend.log en userData");
    }
  }
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
