import path from "node:path";
import { BrowserWindow, screen } from "electron";

export type OverlayPresentation = "hidden" | "listening" | "speaking";

/** Must match frontend/src/overlay/overlayDimensions.ts */
const SPEAKING_WIDTH = 400;
const SPEAKING_MIN_HEIGHT = 152;
const SPEAKING_DEFAULT_HEIGHT = 172;
const SPEAKING_MAX_HEIGHT = 300;

let overlayWindow: BrowserWindow | null = null;
let currentPresentation: OverlayPresentation = "hidden";
let resizeDebounce: ReturnType<typeof setTimeout> | null = null;
let pendingResize: { width: number; height: number } | null = null;
let lastAppliedSpeakingHeight = 0;

export function getOverlayWindow(): BrowserWindow | null {
  return overlayWindow;
}

function listeningAnchorBounds(width: number, height: number) {
  const display = screen.getPrimaryDisplay();
  const { x: areaX, y: areaY } = display.workArea;

  return {
    x: areaX + 16,
    y: areaY + 16,
    width,
    height,
  };
}

function clampSpeakingHeight(height: number): number {
  return Math.min(SPEAKING_MAX_HEIGHT, Math.max(SPEAKING_MIN_HEIGHT, Math.ceil(height)));
}

function speakingAnchorBounds(height: number) {
  const display = screen.getPrimaryDisplay();
  const { width: screenW, height: screenH } = display.workAreaSize;
  const { x: areaX, y: areaY } = display.workArea;
  const clampedHeight = clampSpeakingHeight(height);

  return {
    x: areaX + screenW - SPEAKING_WIDTH - 20,
    y: areaY + Math.round((screenH - clampedHeight) / 2),
    width: SPEAKING_WIDTH,
    height: clampedHeight,
  };
}

export function createOverlayWindow(isDev: boolean): BrowserWindow {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    return overlayWindow;
  }

  overlayWindow = new BrowserWindow({
    width: 1,
    height: 1,
    x: -32000,
    y: -32000,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    hasShadow: false,
    show: false,
    backgroundColor: "#00000000",
    webPreferences: {
      preload: path.join(__dirname, "../preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    void overlayWindow.loadURL("http://127.0.0.1:1420/overlay.html");
  } else {
    void overlayWindow.loadFile(path.join(__dirname, "../dist/overlay.html"));
  }

  overlayWindow.setAlwaysOnTop(true, "screen-saver");
  overlayWindow.on("close", (event) => {
    event.preventDefault();
    overlayWindow?.hide();
  });

  return overlayWindow;
}

export function showOverlayWindow(isDev: boolean): void {
  setOverlayPresentation("speaking", isDev);
}

export function hideOverlayWindow(): void {
  overlayWindow?.hide();
  currentPresentation = "hidden";
  lastAppliedSpeakingHeight = 0;
}

export function resizeOverlayContent(contentWidth: number, contentHeight: number): void {
  pendingResize = { width: contentWidth, height: contentHeight };
  if (resizeDebounce) return;

  resizeDebounce = setTimeout(() => {
    resizeDebounce = null;
    const pending = pendingResize;
    pendingResize = null;
    if (!pending) return;

    const win = overlayWindow;
    if (!win || win.isDestroyed() || !win.isVisible() || currentPresentation === "hidden") return;

    if (currentPresentation === "listening") {
      const width = Math.max(1, Math.ceil(pending.width));
      const height = Math.max(1, Math.ceil(pending.height));
      win.setBounds(listeningAnchorBounds(width, height));
      return;
    }

    const nextHeight = clampSpeakingHeight(pending.height);
    if (lastAppliedSpeakingHeight > 0 && Math.abs(nextHeight - lastAppliedSpeakingHeight) < 4) return;
    lastAppliedSpeakingHeight = nextHeight;
    win.setBounds(speakingAnchorBounds(nextHeight));
  }, 32);
}

/** @deprecated use resizeOverlayContent */
export function resizeSpeakingOverlay(contentWidth: number, contentHeight: number): void {
  resizeOverlayContent(contentWidth, contentHeight);
}

export function setOverlayPresentation(presentation: OverlayPresentation, isDev: boolean): void {
  if (presentation === "hidden") {
    if (currentPresentation === "hidden") return;
    hideOverlayWindow();
    return;
  }

  const unchanged = presentation === currentPresentation;
  currentPresentation = presentation;

  const win = !overlayWindow || overlayWindow.isDestroyed() ? createOverlayWindow(isDev) : overlayWindow;
  if (!win.isVisible()) {
    win.showInactive();
  }

  if (unchanged) return;

  if (presentation === "speaking") {
    lastAppliedSpeakingHeight = 0;
    win.setBounds(speakingAnchorBounds(SPEAKING_DEFAULT_HEIGHT));
    return;
  }

  if (presentation === "listening") {
    win.setBounds(listeningAnchorBounds(220, 44));
  }
}

export function toggleOverlayWindow(isDev: boolean): void {
  if (!overlayWindow || overlayWindow.isDestroyed() || !overlayWindow.isVisible()) {
    showOverlayWindow(isDev);
    return;
  }
  hideOverlayWindow();
}
