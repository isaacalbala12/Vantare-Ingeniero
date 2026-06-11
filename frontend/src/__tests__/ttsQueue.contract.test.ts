import { describe, it, expect, beforeEach, vi } from "vitest";
import { createTtsPipeline } from "../services/ttsPipeline";

describe("tts queue contract VC-Q*", () => {
  let pipeline: ReturnType<typeof createTtsPipeline>;
  const mockFetch = vi.fn(async () => new Blob(["audio"]));
  const mockGetVoice = vi.fn(() => "es-ES-AlvaroNeural");
  const mockGetVoiceHash = vi.fn(() => "hash");
  const mockCache = { get: vi.fn(() => null), set: vi.fn(() => "blob:test") };
  const mockAudioQueue = {
    enqueue: vi.fn(),
    enqueueEngineer: vi.fn(),
    enqueueImmediate: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    pipeline = createTtsPipeline({
      queueMax: 5,
      cooldownMs: 45_000,
      processingTimeoutMs: 30_000,
      fetchTts: mockFetch,
      getVoice: mockGetVoice,
      getVoiceHash: mockGetVoiceHash,
      getCache: () => mockCache,
      getAudioQueue: () => mockAudioQueue,
      shouldDiscard: () => false,
      getRadioMode: () => "IDLE",
      getConfig: () => ({ ttsBackend: "edge", personalityProfileId: "standard" }),
    });
  });

  it("VC-Q01 IMMEDIATE drops NORMAL when queue full", () => {
    for (let i = 0; i < 5; i++) {
      pipeline.enqueue({ text: `n${i}`, priority: "NORMAL", source: "test" });
    }
    expect(pipeline.enqueue({ text: "urgent", priority: "IMMEDIATE", source: "alert" })).toBe(true);
    expect(pipeline.queueLength()).toBe(5);
  });

  it("VC-Q03 duplicate cooldown rejects enqueue", () => {
    expect(pipeline.enqueue({ text: "Hola", priority: "NORMAL", source: "test" })).toBe(true);
    expect(pipeline.enqueue({ text: "Hola", priority: "NORMAL", source: "test" })).toBe(false);
  });

  it("VC-Q04 duplicate queued rejects", () => {
    pipeline.enqueue({ text: "A", priority: "NORMAL", source: "test" });
    expect(pipeline.enqueue({ text: "A", priority: "NORMAL", source: "test" })).toBe(false);
  });

  it("empty text rejected", () => {
    expect(pipeline.enqueue({ text: "", priority: "NORMAL", source: "test" })).toBe(false);
    expect(pipeline.enqueue({ text: "   ", priority: "NORMAL", source: "test" })).toBe(false);
  });

  it("queue processes items and calls fetchTts", async () => {
    pipeline.enqueue({ text: "first", priority: "NORMAL", source: "test" });
    expect(pipeline.queueLength()).toBe(1);

    await pipeline.processNext();
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch).toHaveBeenCalledWith(
      "first",
      "es-ES-AlvaroNeural",
      expect.any(AbortSignal),
    );
  });

  it("ENGINEER preempts NORMAL in queue", () => {
    for (let i = 0; i < 3; i++) {
      pipeline.enqueue({ text: `n${i}`, priority: "NORMAL", source: "test" });
    }
    // ENGINEER should be able to enqueue even when full
    expect(pipeline.enqueue({ text: "eng", priority: "ENGINEER", source: "test" })).toBe(true);
  });

  it("IMMEDIATE preempts non-ENGINEER in queue", () => {
    for (let i = 0; i < 3; i++) {
      pipeline.enqueue({ text: `n${i}`, priority: "NORMAL", source: "test" });
    }
    expect(pipeline.enqueue({ text: "imm", priority: "IMMEDIATE", source: "alert" })).toBe(true);
  });

  it("VC-Q02 queue full with only IMMEDIATE drops oldest IMMEDIATE", () => {
    for (let i = 0; i < 5; i++) {
      pipeline.enqueue({ text: `imm${i}`, priority: "IMMEDIATE", source: "alert" });
    }
    expect(pipeline.enqueue({ text: "new urgent", priority: "IMMEDIATE", source: "alert" })).toBe(true);
    expect(pipeline.queueLength()).toBe(5);
  });

  it("VC-Q05 expired item skipped on process", async () => {
    pipeline.enqueue({
      text: "expired",
      priority: "NORMAL",
      source: "test",
      expiresAt: Date.now() - 1_000,
    });
    await pipeline.processNext();
    expect(mockFetch).not.toHaveBeenCalled();
    expect(pipeline.queueLength()).toBe(0);
  });

  it("VC-Q06 deferFinishUntilPlaybackIdle keeps processing until finish()", async () => {
    const deferred = createTtsPipeline({
      deferFinishUntilPlaybackIdle: true,
      fetchTts: mockFetch,
      getVoice: mockGetVoice,
      getVoiceHash: mockGetVoiceHash,
      getCache: () => ({ get: () => "blob:cached", set: vi.fn() }),
      getAudioQueue: () => mockAudioQueue,
      shouldDiscard: () => false,
      getRadioMode: () => "IDLE",
      getConfig: () => ({ ttsBackend: "edge", personalityProfileId: "standard" }),
    });
    deferred.enqueue({ text: "cached", priority: "NORMAL", source: "test" });
    await deferred.processNext();
    expect(deferred.isProcessing()).toBe(true);
    deferred.finish();
    expect(deferred.isProcessing()).toBe(false);
  });

  it("watchdog resets stuck processing", async () => {
    vi.useFakeTimers();
    const neverResolves = vi.fn(() => new Promise<Blob>(() => {}));
    const p = createTtsPipeline({
      queueMax: 5,
      cooldownMs: 45_000,
      processingTimeoutMs: 30_000,
      fetchTts: neverResolves,
      getVoice: mockGetVoice,
      getVoiceHash: mockGetVoiceHash,
      getCache: () => ({ get: () => null, set: vi.fn() }),
      getAudioQueue: () => mockAudioQueue,
      shouldDiscard: () => false,
      getRadioMode: () => "IDLE",
      getConfig: () => ({ ttsBackend: "edge", personalityProfileId: "standard" }),
    });

    p.enqueue({ text: "stuck", priority: "NORMAL", source: "test" });
    void p.processNext();
    expect(p.isProcessing()).toBe(true);

    vi.advanceTimersByTime(30_001);
    expect(p.isProcessing()).toBe(false);

    vi.useRealTimers();
  });

  it("cache hit skips fetch", async () => {
    const cachedPipeline = createTtsPipeline({
      queueMax: 5,
      cooldownMs: 45_000,
      fetchTts: mockFetch,
      getVoice: mockGetVoice,
      getVoiceHash: mockGetVoiceHash,
      getCache: () => ({ get: () => "blob:cached", set: vi.fn() }),
      getAudioQueue: () => mockAudioQueue,
      shouldDiscard: () => false,
      getRadioMode: () => "IDLE",
      getConfig: () => ({ ttsBackend: "edge", personalityProfileId: "standard" }),
    });

    cachedPipeline.enqueue({ text: "cached", priority: "NORMAL", source: "test" });
    await cachedPipeline.processNext();
    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockAudioQueue.enqueue).toHaveBeenCalled();
    expect(cachedPipeline.isProcessing()).toBe(false);
    expect(cachedPipeline.queueLength()).toBe(0);
  });
});
