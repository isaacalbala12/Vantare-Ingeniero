import { useEffect } from "react";
import { useAppStore } from "../../store/config";
import { subscribeOverlaySync } from "./overlayBroadcast";

/** Overlay window: receive live radio state from hub (single WebSocket owner). */
export function useOverlayStateSync(): void {
  useEffect(() => {
    return subscribeOverlaySync(({ radio }) => {
      useAppStore.setState((state) => {
        if (
          state.radio.mode === radio.mode &&
          state.radio.voicePlaybackText === radio.voicePlaybackText
        ) {
          return state;
        }
        return {
          radio: {
            ...state.radio,
            mode: radio.mode,
            voicePlaybackText: radio.voicePlaybackText,
          },
        };
      });
    });
  }, []);
}

