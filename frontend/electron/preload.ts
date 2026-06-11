import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("vantare", {
  isElectron: true as const,
  openExternal: (url: string) => ipcRenderer.invoke("shell:openExternal", url),
  duckLmu: (active: boolean, level = 0.65) =>
    ipcRenderer.invoke("audio:duckLmu", { active, level }),
  saveSessionHistory: (payload: unknown) => ipcRenderer.invoke("history:save", payload),
  listSessionHistories: () => ipcRenderer.invoke("history:list") as Promise<string[]>,
  loadSessionHistory: (filename: string) => ipcRenderer.invoke("history:load", filename),
  setOverlayResizeMode: (enabled: boolean) =>
    ipcRenderer.invoke("overlay:setResizeMode", enabled),
  toggleOverlay: () => ipcRenderer.invoke("overlay:toggle"),
  showOverlay: () => ipcRenderer.invoke("overlay:show"),
  hideOverlay: () => ipcRenderer.invoke("overlay:hide"),
  setOverlayPresentation: (presentation: "hidden" | "listening" | "speaking") =>
    ipcRenderer.invoke("overlay:setPresentation", presentation),
  reportOverlaySize: (size: { width: number; height: number }) =>
    ipcRenderer.send("overlay:resizeContent", size),
  publishGamepadEdge: (payload: { pad: number; button: number; down: boolean }) =>
    ipcRenderer.send("gamepad:edge", payload),
  subscribePtt: (handler: (action: "down" | "up" | "toggle") => void) => {
    const onDown = () => handler("down");
    const onUp = () => handler("up");
    const onToggle = () => handler("toggle");
    ipcRenderer.on("ptt:down", onDown);
    ipcRenderer.on("ptt:up", onUp);
    ipcRenderer.on("ptt:toggle", onToggle);
    return () => {
      ipcRenderer.removeListener("ptt:down", onDown);
      ipcRenderer.removeListener("ptt:up", onUp);
      ipcRenderer.removeListener("ptt:toggle", onToggle);
    };
  },
  updatePttHotkeys: (payload: { start: string; stop: string }) =>
    ipcRenderer.invoke("ptt:updateHotkeys", payload),
  getDesktopUpdateStatus: () => ipcRenderer.invoke("desktop-update:getStatus"),
  checkDesktopUpdates: () => ipcRenderer.invoke("desktop-update:check"),
  downloadDesktopUpdate: () => ipcRenderer.invoke("desktop-update:download"),
  quitAndInstallDesktopUpdate: () => ipcRenderer.invoke("desktop-update:quitAndInstall"),
  subscribeDesktopUpdate: (handler: (status: unknown) => void) => {
    const listener = (_event: unknown, status: unknown) => handler(status);
    ipcRenderer.on("desktop-update:status", listener);
    return () => ipcRenderer.removeListener("desktop-update:status", listener);
  },
  publishOverlayState: (payload: unknown) => ipcRenderer.send("overlay:publishState", payload),
  subscribeOverlayState: (handler: (payload: unknown) => void) => {
    const listener = (_event: unknown, payload: unknown) => handler(payload);
    ipcRenderer.on("overlay:state", listener);
    return () => ipcRenderer.removeListener("overlay:state", listener);
  },
});
