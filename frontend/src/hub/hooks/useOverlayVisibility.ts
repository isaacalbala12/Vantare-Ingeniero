import { useLayoutEffect, useRef } from "react";
import { useAppStore } from "../../store/config";
import { getPlatform } from "../../core/platform";
import {
  radioModeToOverlayPresentation,
  type OverlayPresentation,
} from "../../overlay/overlayPresentation";

/** Hub: show/hide/resize the Electron overlay from radio mode (PTT + TTS). */
export function useOverlayVisibility(): void {
  const mode = useAppStore((s) => s.radio.mode);
  const lastPresentation = useRef<OverlayPresentation | null>(null);

  useLayoutEffect(() => {
    const platform = getPlatform();
    if (!platform.isElectron || !platform.setOverlayPresentation) return;

    const presentation = radioModeToOverlayPresentation(mode);
    if (lastPresentation.current === presentation) return;
    lastPresentation.current = presentation;
    void platform.setOverlayPresentation(presentation);
  }, [mode]);
}
