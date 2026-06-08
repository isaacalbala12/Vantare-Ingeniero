import type { ElectronBridge } from "../core/platform/types";

declare global {
  interface Window {
    vantare?: ElectronBridge;
  }
}

export {};
