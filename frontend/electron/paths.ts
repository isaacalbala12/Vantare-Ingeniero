import path from "node:path";
import { app } from "electron";

/** Packaged renderer HTML (dist/index.html, dist/overlay.html). */
export function rendererHtml(name: string): string {
  return path.join(app.getAppPath(), "dist", name);
}

/** Preload script next to electron-dist root (works from windows/ subfolder). */
export function preloadScriptPath(): string {
  return path.join(__dirname, "../preload.js");
}
