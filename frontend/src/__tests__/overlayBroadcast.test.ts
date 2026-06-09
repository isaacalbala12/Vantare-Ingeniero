import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { publishOverlaySync, subscribeOverlaySync } from "../core/sync/overlayBroadcast";

describe("overlayBroadcast", () => {
  const listeners = new Map<string, Set<(event: MessageEvent) => void>>();

  beforeEach(() => {
    listeners.clear();
    vi.stubGlobal(
      "BroadcastChannel",
      class {
        readonly name: string;
        private handler: ((event: MessageEvent) => void) | null = null;

        constructor(name: string) {
          this.name = name;
          if (!listeners.has(name)) listeners.set(name, new Set());
        }

        set onmessage(handler: ((event: MessageEvent) => void) | null) {
          if (this.handler) listeners.get(this.name)?.delete(this.handler);
          this.handler = handler;
          if (handler) listeners.get(this.name)?.add(handler);
        }

        get onmessage() {
          return this.handler;
        }

        postMessage(data: unknown) {
          const event = { data } as MessageEvent;
          listeners.get(this.name)?.forEach((handler) => handler(event));
        }

        close() {
          if (this.handler) listeners.get(this.name)?.delete(this.handler);
        }
      },
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("delivers published radio payload to subscriber", () => {
    const received: unknown[] = [];
    const unsubscribe = subscribeOverlaySync((payload) => received.push(payload));

    publishOverlaySync({
      radio: {
        mode: "IDLE",
        voicePlaybackText: "",
      },
    });

    expect(received).toHaveLength(1);
    expect((received[0] as { radio: { mode: string } }).radio.mode).toBe("IDLE");
    unsubscribe();
  });
});
