import { describe, it, expect, beforeEach, vi } from "vitest";
import { priorityAudioQueue } from "../services/priorityAudioQueue";

describe("priorityAudioQueue delayed playback", () => {
  beforeEach(() => {
    priorityAudioQueue.stopAll();
    vi.restoreAllMocks();
  });

  it("retiene NORMAL hasta delayedUntilMs", async () => {
    const playOrder: string[] = [];
    const originalAudio = globalThis.Audio;

    class MockAudio {
      src = "";
      volume = 1;
      preload = "auto";
      onended: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(public url: string) {
        this.src = url;
      }
      async play() {
        playOrder.push(this.url);
        queueMicrotask(() => this.onended?.());
      }
      pause() {}
    }

    // @ts-expect-error test mock
    globalThis.Audio = MockAudio;

    priorityAudioQueue.enqueue({
      text: "gap",
      url: "blob:delayed",
      priority: "NORMAL",
      preemptible: true,
      source: "engineer",
      delayedUntilMs: Date.now() + 40,
    });

    await new Promise((r) => setTimeout(r, 10));
    expect(playOrder).toEqual([]);

    await new Promise((r) => setTimeout(r, 50));
    expect(playOrder).toEqual(["blob:delayed"]);

    globalThis.Audio = originalAudio;
  });
});
