import type { RadioMode } from "../store/config";

export type OverlayPresentation = "hidden" | "listening" | "speaking";

export function radioModeToOverlayPresentation(mode: RadioMode): OverlayPresentation {
  switch (mode) {
    case "LISTENING_PILOT":
      return "listening";
    case "SPEAKING_ENGINE":
      return "speaking";
    default:
      return "hidden";
  }
}
