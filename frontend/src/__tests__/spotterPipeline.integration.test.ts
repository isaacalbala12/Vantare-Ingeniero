import { describe, it, expect, beforeEach, vi } from "vitest";
import { shouldVoiceAlert } from "../services/alertVoice";
import { classifyTtsPriority } from "../services/spotterPhrases";
import { ttsCache, buildVoiceHash } from "../services/ttsCache";
import { priorityAudioQueue } from "../services/priorityAudioQueue";

describe("spotterPipeline integration (mock)", () => {
  beforeEach(() => {
    ttsCache.clear();
    priorityAudioQueue.stopAll();
  });

  it("alert proximity → voice → cache → IMMEDIATE queue", async () => {
    const payload = {
      event: "alert",
      category: "proximity",
      severity: "INFO",
      audio_priority: "2",
      message: "Hypercar doblando por la derecha",
    };

    expect(shouldVoiceAlert(payload)).toBe(true);
    expect(classifyTtsPriority(payload.message, payload)).toBe("IMMEDIATE");

    const blob = new Blob(["fake-audio"], { type: "audio/mpeg" });
    const url = ttsCache.set(payload.message, buildVoiceHash({}), blob);
    expect(ttsCache.get(payload.message, buildVoiceHash({}))).toBe(url);

    const playSpy = vi.fn(async () => {});
    const originalAudio = globalThis.Audio;

    class MockAudio {
      onended: (() => void) | null = null;
      onerror: (() => void) | null = null;
      volume = 1;
      preload = "auto";
      constructor(public src: string) {}
      async play() {
        playSpy(this.src);
        queueMicrotask(() => this.onended?.());
      }
      pause() {}
    }

    // @ts-expect-error test mock
    globalThis.Audio = MockAudio;

    priorityAudioQueue.enqueueImmediate({
      text: payload.message,
      url,
      priority: "IMMEDIATE",
      preemptible: false,
      source: "alert",
    });

    await new Promise((r) => setTimeout(r, 30));
    expect(playSpy).toHaveBeenCalledWith(url);

    globalThis.Audio = originalAudio;
  });
});
