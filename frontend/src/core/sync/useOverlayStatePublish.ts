import { useEffect, useRef } from "react";

import { useAppStore } from "../../store/config";

import { publishOverlaySync } from "./overlayBroadcast";

const TEXT_THROTTLE_MS = 120;

/** Hub window: push minimal radio state to overlay (no telemetry, throttled text). */
export function useOverlayStatePublish(): void {
  const mode = useAppStore((s) => s.radio.mode);
  const voicePlaybackText = useAppStore((s) => s.radio.voicePlaybackText);
  const lastPublishedMode = useRef(mode);
  const lastPublishedText = useRef(voicePlaybackText);
  const pendingText = useRef(voicePlaybackText);
  const textTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    pendingText.current = voicePlaybackText;

    if (lastPublishedMode.current !== mode) {
      if (textTimer.current) {
        clearTimeout(textTimer.current);
        textTimer.current = null;
      }
      lastPublishedMode.current = mode;
      lastPublishedText.current = voicePlaybackText;
      publishOverlaySync({ radio: { mode, voicePlaybackText } });
      return;
    }

    if (voicePlaybackText === lastPublishedText.current) {
      return;
    }

    if (textTimer.current) {
      clearTimeout(textTimer.current);
    }

    textTimer.current = setTimeout(() => {
      textTimer.current = null;
      lastPublishedText.current = pendingText.current;
      publishOverlaySync({
        radio: { mode, voicePlaybackText: pendingText.current },
      });
    }, TEXT_THROTTLE_MS);

    return () => {
      if (textTimer.current) {
        clearTimeout(textTimer.current);
        textTimer.current = null;
      }
    };
  }, [mode, voicePlaybackText]);
}
