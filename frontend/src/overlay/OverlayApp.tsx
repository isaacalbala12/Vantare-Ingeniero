import { useAppStore } from "../store/config";
import { useOverlayStateSync } from "../core/sync/useOverlayStateSync";
import { radioModeToOverlayPresentation } from "./overlayPresentation";
import { useOverlayContentSize } from "./useOverlayContentSize";
import { A1ListeningChip } from "./variants/A1ListeningChip";
import { A1SpeakingCard } from "./variants/A1SpeakingCard";

export function OverlayApp() {
  useOverlayStateSync();
  const presentation = useAppStore((s) => radioModeToOverlayPresentation(s.radio.mode));
  const contentRef = useOverlayContentSize(presentation !== "hidden", presentation);

  if (presentation === "hidden") {
    return null;
  }

  return (
    <div className="pointer-events-none w-fit h-fit bg-transparent overflow-visible">
      <div ref={contentRef} className="w-fit h-fit">
        {presentation === "listening" ? <A1ListeningChip /> : null}
        {presentation === "speaking" ? <A1SpeakingCard /> : null}
      </div>
    </div>
  );
}

export default OverlayApp;
