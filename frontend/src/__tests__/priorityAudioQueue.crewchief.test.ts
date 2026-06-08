import { describe, it, expect, beforeEach, vi } from "vitest";
import { priorityAudioQueue, type AudioItem } from "../services/priorityAudioQueue";

function item(overrides: Partial<AudioItem>): AudioItem {
  return {
    text: "mensaje",
    url: "blob:message",
    priority: "NORMAL",
    preemptible: true,
    source: "test",
    expiresAt: undefined,
    playEvenWhenSilenced: false,
    ...overrides,
  };
}

describe("Crew Chief priorityAudioQueue behavior", () => {
  beforeEach(() => {
    priorityAudioQueue.stopAll();
    vi.restoreAllMocks();
  });

  it("drops expired items before playback", async () => {
    const played: string[] = [];
    const originalAudio = globalThis.Audio;
    class MockAudio {
      volume = 1;
      preload = "auto";
      onended: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(public url: string) {}
      async play() {
        played.push(this.url);
        queueMicrotask(() => this.onended?.());
      }
      pause() {}
    }
    // @ts-expect-error test mock
    globalThis.Audio = MockAudio;

    priorityAudioQueue.enqueue(item({ url: "blob:expired", expiresAt: Date.now() - 1 }));
    priorityAudioQueue.enqueue(item({ url: "blob:fresh", expiresAt: Date.now() + 5000 }));

    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(played).toEqual(["blob:fresh"]);

    globalThis.Audio = originalAudio;
  });

  it("keeps immediate messages when normal queue is stopped", () => {
    priorityAudioQueue.enqueue(item({ priority: "IMMEDIATE", preemptible: false, url: "blob:imm" }));
    priorityAudioQueue.enqueue(item({ priority: "NORMAL", url: "blob:norm" }));

    priorityAudioQueue.stopNormal();

    expect(priorityAudioQueue.debugSnapshot().immediate).toBe(1);
    expect(priorityAudioQueue.debugSnapshot().normal).toBe(0);
  });
});
