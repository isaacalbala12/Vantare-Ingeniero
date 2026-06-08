import type { RadioMode } from "../../store/config";

export const OVERLAY_SYNC_CHANNEL = "vantare-overlay-sync";

/** Minimal payload — overlay UI only reads mode + spoken text. */
export type OverlaySyncPayload = {
  radio: {
    mode: RadioMode;
    voicePlaybackText: string;
  };
};

let overlayPublishChannel: BroadcastChannel | null = null;

function getOverlayPublishChannel(): BroadcastChannel | null {
  if (typeof BroadcastChannel === "undefined") return null;
  if (!overlayPublishChannel) {
    overlayPublishChannel = new BroadcastChannel(OVERLAY_SYNC_CHANNEL);
  }
  return overlayPublishChannel;
}

export function publishOverlaySync(payload: OverlaySyncPayload): void {
  getOverlayPublishChannel()?.postMessage(payload);
}

export function subscribeOverlaySync(
  handler: (payload: OverlaySyncPayload) => void,
): () => void {
  if (typeof BroadcastChannel === "undefined") return () => {};
  const channel = new BroadcastChannel(OVERLAY_SYNC_CHANNEL);
  channel.onmessage = (event: MessageEvent<OverlaySyncPayload>) => {
    handler(event.data);
  };
  return () => channel.close();
}
