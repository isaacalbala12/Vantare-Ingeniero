import { useLayoutEffect } from "react";
import type { RadioMode } from "../store/config";
import { getPlatform } from "../core/platform";
import { radioModeToOverlayPresentation } from "./overlayPresentation";

/** Overlay window: keep Electron bounds in sync with local radio mode. */
export function useOverlayWindowLifecycle(mode: RadioMode): void {
  useLayoutEffect(() => {
    const platform = getPlatform();
    if (!platform.isElectron || !platform.setOverlayPresentation) return;
    void platform.setOverlayPresentation(radioModeToOverlayPresentation(mode));
  }, [mode]);
}
