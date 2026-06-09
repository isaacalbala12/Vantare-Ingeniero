import path from "node:path";
import { BrowserWindow, ipcMain } from "electron";

type PadEdge = { pad: number; button: number; down: boolean };

let pollWindow: BrowserWindow | null = null;
let startTarget: { pad: number; button: number } | null = null;
let stopTarget: { pad: number; button: number } | null = null;
let toggleMode = true;
let hubWindowRef: BrowserWindow | null = null;
const pressed = new Set<string>();

function padKey(pad: number, button: number): string {
  return `${pad}:${button}`;
}

function parsePadHotkey(raw: string): { pad: number; button: number } | null {
  const match = raw.trim().match(/^Pad(\d+):B(\d+)$/i);
  if (!match) return null;
  return { pad: Number(match[1]), button: Number(match[2]) };
}

function sendPtt(action: "down" | "up" | "toggle"): void {
  const hub = hubWindowRef;
  if (!hub || hub.isDestroyed()) return;
  hub.webContents.send(`ptt:${action}`);
}

function handleEdge({ pad, button, down }: PadEdge): void {
  const key = padKey(pad, button);
  const wasPressed = pressed.has(key);
  if (down === wasPressed) return;

  if (down) pressed.add(key);
  else pressed.delete(key);

  const isStart = startTarget && startTarget.pad === pad && startTarget.button === button;
  const isStop = stopTarget && stopTarget.pad === pad && stopTarget.button === button;

  if (toggleMode && isStart && down) {
    sendPtt("toggle");
    return;
  }

  if (isStart && down) sendPtt("down");
  if (isStop && !down) sendPtt("up");
}

function ensurePollWindow(): BrowserWindow {
  if (pollWindow && !pollWindow.isDestroyed()) return pollWindow;

  pollWindow = new BrowserWindow({
    width: 1,
    height: 1,
    x: -200,
    y: -200,
    show: false,
    frame: false,
    skipTaskbar: true,
    webPreferences: {
      preload: path.join(__dirname, "../preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });

  const html = `<!doctype html><html><body><script>
    setInterval(() => {
      const pads = navigator.getGamepads ? navigator.getGamepads() : [];
      for (let i = 0; i < pads.length; i++) {
        const pad = pads[i];
        if (!pad) continue;
        for (let b = 0; b < pad.buttons.length; b++) {
          const pressed = !!pad.buttons[b]?.pressed;
          window.vantare?.publishGamepadEdge?.({ pad: i, button: b, down: pressed });
        }
      }
    }, 25);
  </script></body></html>`;

  void pollWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
  return pollWindow;
}

export function configureGamepadPoll(
  hubWindow: BrowserWindow | null,
  hotkeys: { start: string; stop: string },
): void {
  hubWindowRef = hubWindow;
  startTarget = parsePadHotkey(hotkeys.start);
  stopTarget = parsePadHotkey(hotkeys.stop);
  toggleMode = hotkeys.start.trim().toLowerCase() === hotkeys.stop.trim().toLowerCase();
  pressed.clear();

  if (!startTarget && !stopTarget) {
    destroyPollWindow();
    return;
  }

  ensurePollWindow();
}

export function destroyPollWindow(): void {
  if (pollWindow && !pollWindow.isDestroyed()) {
    pollWindow.destroy();
  }
  pollWindow = null;
  pressed.clear();
}

export function registerGamepadIpc(): void {
  ipcMain.on("gamepad:edge", (_event, payload: PadEdge) => {
    if (!payload || typeof payload.pad !== "number" || typeof payload.button !== "number") return;
    handleEdge(payload);
  });
}
