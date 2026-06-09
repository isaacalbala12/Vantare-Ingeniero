import { globalShortcut } from "electron";
import type { BrowserWindow } from "electron";
import { toElectronAccelerator } from "./accelerator";
import { configureGamepadPoll, destroyPollWindow } from "./gamepadPoll";
import { getOverlayWindow } from "../windows/overlayWindow";

const OVERLAY_RESIZE_HOTKEY = "Control+Shift+O";

export interface PttHotkeyConfig {
  start: string;
  stop: string;
}

let current: PttHotkeyConfig = { start: "Ctrl+Shift+Space", stop: "Ctrl+Shift+Space" };

function sendPttToggle(hubWindow: BrowserWindow | null): void {
  if (hubWindow && !hubWindow.isDestroyed()) {
    hubWindow.webContents.send("ptt:toggle");
  }
}

function sendPttDown(hubWindow: BrowserWindow | null): void {
  if (hubWindow && !hubWindow.isDestroyed()) {
    hubWindow.webContents.send("ptt:down");
  }
}

function sendPttUp(hubWindow: BrowserWindow | null): void {
  if (hubWindow && !hubWindow.isDestroyed()) {
    hubWindow.webContents.send("ptt:up");
  }
}

function isMouseHotkey(hk: string): boolean {
  return hk.startsWith("Mouse");
}

function isGamepadHotkey(hk: string): boolean {
  return /^Pad\d+:B\d+$/i.test(hk.trim());
}

function isToggleMode(hotkeys: PttHotkeyConfig): boolean {
  return hotkeys.start.toLowerCase() === hotkeys.stop.toLowerCase();
}

export async function registerPttShortcuts(
  hubWindow: BrowserWindow | null,
  hotkeys: PttHotkeyConfig = current,
): Promise<void> {
  current = hotkeys;
  unregisterPttShortcuts();

  const toggle = isToggleMode(hotkeys);

  if (!isMouseHotkey(hotkeys.start) && !isGamepadHotkey(hotkeys.start)) {
    const startAcc = toElectronAccelerator(hotkeys.start);
    const startHandler = toggle
      ? () => sendPttToggle(hubWindow)
      : () => sendPttDown(hubWindow);
    const ok = globalShortcut.register(startAcc, startHandler);
    if (!ok) console.warn("[electron] failed to register PTT start:", startAcc);
  }

  if (!toggle && !isMouseHotkey(hotkeys.stop) && !isGamepadHotkey(hotkeys.stop)) {
    const stopAcc = toElectronAccelerator(hotkeys.stop);
    const ok = globalShortcut.register(stopAcc, () => sendPttUp(hubWindow));
    if (!ok) console.warn("[electron] failed to register PTT stop:", stopAcc);
  }

  globalShortcut.register(OVERLAY_RESIZE_HOTKEY, () => {
    const overlay = getOverlayWindow();
    if (!overlay || overlay.isDestroyed()) return;
    overlay.setResizable(!overlay.isResizable());
  });

  configureGamepadPoll(hubWindow, hotkeys);
}

export function unregisterPttShortcuts(): void {
  globalShortcut.unregisterAll();
  destroyPollWindow();
}
