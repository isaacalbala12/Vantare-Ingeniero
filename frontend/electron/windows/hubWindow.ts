import path from "node:path";
import { BrowserWindow } from "electron";

export function createHubWindow(isDev: boolean): BrowserWindow {
  const win = new BrowserWindow({
    width: 1920,
    height: 1080,
    minWidth: 1024,
    minHeight: 640,
    show: false,
    title: "Vantare Ingeniero",
    backgroundColor: "#09090b",
    webPreferences: {
      preload: path.join(__dirname, "../preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.once("ready-to-show", () => win.show());

  if (isDev) {
    void win.loadURL("http://127.0.0.1:1420");
  } else {
    void win.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  win.on("close", (event) => {
    if (process.platform !== "darwin") {
      event.preventDefault();
      win.hide();
    }
  });

  return win;
}
