import type { RadioMode } from "../../store/config";

export const OVERLAY_SYNC_CHANNEL = "vantare-overlay-sync";

/** Minimal payload — overlay UI only reads mode + spoken text. */
export type OverlaySyncPayload = {
  radio: {
    mode: RadioMode;
    voicePlaybackText: string;
  };
};

type OverlayBridge = {
  publishOverlayState?: (payload: OverlaySyncPayload) => void;
  subscribeOverlayState?: (handler: (payload: OverlaySyncPayload) => void) => () => void;
};

function getOverlayBridge(): OverlayBridge | undefined {
  return (window as Window & { vantare?: OverlayBridge }).vantare;
}

let overlayPublishChannel: BroadcastChannel | null = null;

function getOverlayPublishChannel(): BroadcastChannel | null {
  if (typeof BroadcastChannel === "undefined") return null;
  if (!overlayPublishChannel) {
    overlayPublishChannel = new BroadcastChannel(OVERLAY_SYNC_CHANNEL);
  }
  return overlayPublishChannel;
}

export function publishOverlaySync(payload: OverlaySyncPayload): void {
  const bridge = getOverlayBridge();
  if (bridge?.publishOverlayState) {
    bridge.publishOverlayState(payload);
    return;
  }
  getOverlayPublishChannel()?.postMessage(payload);
}

export function subscribeOverlaySync(
  handler: (payload: OverlaySyncPayload) => void,
): () => void {
  const bridge = getOverlayBridge();
  if (bridge?.subscribeOverlayState) {
    return bridge.subscribeOverlayState(handler);
  }
  if (typeof BroadcastChannel === "undefined") return () => {};
  const channel = new BroadcastChannel(OVERLAY_SYNC_CHANNEL);
  channel.onmessage = (event: MessageEvent<OverlaySyncPayload>) => {
    handler(event.data);
  };
  return () => channel.close();
}
