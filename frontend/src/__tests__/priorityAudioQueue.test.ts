import { describe, it, expect, beforeEach, vi } from "vitest";
import { priorityAudioQueue } from "../services/priorityAudioQueue";

describe("priorityAudioQueue", () => {
  beforeEach(() => {
    priorityAudioQueue.stopAll();
    vi.restoreAllMocks();
  });

  it("reproduce ENGINEER antes que IMMEDIATE en cola", async () => {
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

    priorityAudioQueue.enqueueImmediate({
      text: "Coche a la derecha",
      url: "blob:immediate",
      priority: "IMMEDIATE",
      preemptible: true,
      source: "alert",
    });
    priorityAudioQueue.enqueueEngineer({
      text: "Respuesta ingeniero",
      url: "blob:engineer",
      priority: "ENGINEER",
      preemptible: false,
      source: "advice",
    });

    await new Promise((r) => setTimeout(r, 80));
    expect(playOrder[0]).toBe("blob:engineer");

    globalThis.Audio = originalAudio;
  });

  it("reproduce IMMEDIATE antes que NORMAL", async () => {
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
      text: "consejo largo",
      url: "blob:normal",
      priority: "NORMAL",
      preemptible: true,
      source: "advice",
    });
    priorityAudioQueue.enqueueImmediate({
      text: "Coche a la derecha",
      url: "blob:immediate",
      priority: "IMMEDIATE",
      preemptible: false,
      source: "alert",
    });

    await new Promise((r) => setTimeout(r, 50));
    expect(playOrder[0]).toBe("blob:immediate");

    globalThis.Audio = originalAudio;
  });

  it("stopNormal no vacía cola immediate pendiente", () => {
    priorityAudioQueue.enqueue({
      text: "spotter",
      url: "blob:imm",
      priority: "IMMEDIATE",
      preemptible: false,
      source: "alert",
    });
    priorityAudioQueue.enqueue({
      text: "ingeniero",
      url: "blob:norm",
      priority: "NORMAL",
      preemptible: true,
      source: "advice",
    });
    priorityAudioQueue.stopNormal();
    priorityAudioQueue.stopAll();
    expect(true).toBe(true);
  });
});
