// TTS Pipeline — cola, procesamiento, watchdog. Usado por useWebSocket.ts.

import { isExpiredAt } from "./alertExpiry";
import type { TtsPriority as SpotterTtsPriority } from "./spotterPhrases";
import { audioQueue } from "./audioQueue";

export type TtsPriority = "ENGINEER" | "IMMEDIATE" | "NORMAL";

export type TtsQueueItem = {
  text: string;
  priority: TtsPriority;
  source: string;
  voiceRole: "engineer" | "spotter";
  expiresAt?: number;
  delayedUntilMs?: number;
  validationKey?: string;
};

const TTS_QUEUE_MAX = 5;
const TTS_SPOKEN_COOLDOWN_MS = 45_000;
const TTS_IMMEDIATE_COOLDOWN_MS = 2_500;
const TTS_FETCH_TIMEOUT_MS = 20_000;
const DEFAULT_WATCHDOG_MS = 30_000;

function ttsPriorityRank(priority: TtsPriority): number {
  if (priority === "ENGINEER") return 3;
  if (priority === "IMMEDIATE") return 2;
  return 1;
}

function sortTtsQueue(items: TtsQueueItem[]): void {
  items.sort((a, b) => ttsPriorityRank(b.priority) - ttsPriorityRank(a.priority));
}

function ttsCacheKey(text: string): string {
  return text.length > 2000 ? `${text.slice(0, 1997)}...` : text;
}

export type TtsPipelineOptions = {
  queueMax?: number;
  cooldownMs?: number;
  processingTimeoutMs?: number;
  fetchTts: (text: string, voice: string, signal?: AbortSignal) => Promise<Blob | null>;
  getVoice: (role: "engineer" | "spotter") => string;
  getVoiceHash: (params: { ttsBackend: string; ttsVoice: string; role: string; profileId: string }) => string;
  getCache: () => { get: (text: string, hash: string) => string | null; set: (text: string, hash: string, blob: Blob) => string };
  getAudioQueue?: () => typeof audioQueue;
  shouldDiscard: (radioMode: string) => boolean;
  getRadioMode: () => string;
  getConfig: () => Record<string, unknown>;
  shouldDeferItem?: (item: TtsQueueItem) => boolean;
  onProcessingChange?: (busy: boolean) => void;
  /** Production: true — finish() when audioQueue idle. Tests: false — finish after dispatch. */
  deferFinishUntilPlaybackIdle?: boolean;
};

export function createTtsPipeline(options: TtsPipelineOptions) {
  const queueMax = options.queueMax ?? TTS_QUEUE_MAX;
  const cooldownMs = options.cooldownMs ?? TTS_SPOKEN_COOLDOWN_MS;
  const watchdogMs = options.processingTimeoutMs ?? DEFAULT_WATCHDOG_MS;
  const deferFinishUntilPlaybackIdle = options.deferFinishUntilPlaybackIdle ?? false;

  const queue: TtsQueueItem[] = [];
  const spokenAt = new Map<string, number>();
  let processing = false;
  let currentPriority: TtsPriority | null = null;
  let watchdogTimer: ReturnType<typeof setTimeout> | null = null;
  let deferTimer: ReturnType<typeof setTimeout> | null = null;
  let abortController: AbortController | null = null;
  let abortIntentional = false;

  function clearWatchdog(): void {
    if (watchdogTimer) {
      clearTimeout(watchdogTimer);
      watchdogTimer = null;
    }
  }

  function clearDeferTimer(): void {
    if (deferTimer) {
      clearTimeout(deferTimer);
      deferTimer = null;
    }
  }

  function startWatchdog(): void {
    clearWatchdog();
    watchdogTimer = setTimeout(() => {
      console.warn("[TTS] tts_stuck_processing — watchdog reset");
      finish();
    }, watchdogMs);
  }

  function enqueue(
    item: Omit<TtsQueueItem, "voiceRole"> & { voiceRole?: "engineer" | "spotter" },
  ): boolean {
    const trimmed = item.text.trim();
    if (!trimmed) return false;

    const fullItem: TtsQueueItem = { ...item, voiceRole: item.voiceRole ?? "engineer" };

    const now = performance.now();
    const cooldown = fullItem.priority === "IMMEDIATE" ? TTS_IMMEDIATE_COOLDOWN_MS : cooldownMs;
    const lastSpoken = spokenAt.get(trimmed);
    if (lastSpoken !== undefined && now - lastSpoken < cooldown) {
      return false;
    }
    if (queue.some((q) => q.text === trimmed)) {
      return false;
    }

    if (queue.length >= queueMax) {
      if (fullItem.priority === "IMMEDIATE") {
        const normalIdx = queue.findIndex((q) => q.priority === "NORMAL");
        if (normalIdx >= 0) {
          queue.splice(normalIdx, 1);
        } else {
          const immIdx = queue.findIndex((q) => q.priority === "IMMEDIATE");
          if (immIdx >= 0) {
            queue.splice(immIdx, 1);
          } else {
            console.warn("[WS] Cola TTS llena — no se pudo encolar alerta IMMEDIATE");
            return false;
          }
        }
      } else if (fullItem.priority === "ENGINEER") {
        const dropIdx = queue.findIndex((q) => q.priority !== "ENGINEER");
        if (dropIdx >= 0) {
          queue.splice(dropIdx, 1);
        } else {
          console.warn("[WS] Cola TTS llena — descartando mensaje ENGINEER antiguo");
          queue.shift();
        }
      } else {
        console.warn("[WS] Cola TTS llena — descartando mensaje");
        return false;
      }
    }

    spokenAt.set(trimmed, now);
    queue.push(fullItem);
    sortTtsQueue(queue);

    // IMMEDIATE no aborta síntesis ENGINEER en curso (I6)
    if (
      fullItem.priority === "IMMEDIATE" &&
      processing &&
      currentPriority !== "ENGINEER" &&
      abortController
    ) {
      abortIntentional = true;
      abortController.abort();
      abortController = null;
      processing = false;
      currentPriority = null;
      abortIntentional = false;
    }

    return true;
  }

  async function processNext(): Promise<void> {
    if (processing || queue.length === 0) return;
    processing = true;
    options.onProcessingChange?.(true);
    startWatchdog();

    sortTtsQueue(queue);

    while (queue.length > 0 && isExpiredAt(queue[0].expiresAt)) {
      queue.shift();
    }
    if (queue.length === 0) {
      finish();
      return;
    }

    const peek = queue[0];
    if (options.shouldDeferItem?.(peek)) {
      peek.delayedUntilMs = performance.now() + 300;
      processing = false;
      currentPriority = null;
      options.onProcessingChange?.(false);
      clearWatchdog();
      clearDeferTimer();
      deferTimer = setTimeout(() => {
        deferTimer = null;
        void processNext();
      }, 300);
      return;
    }

    const head = queue.shift()!;
    currentPriority = head.priority;

    const cfg = options.getConfig();
    const ttsBackend = String(cfg.ttsBackend ?? "edge");
    const personalityProfileId = String(cfg.personalityProfileId ?? "standard");
    const cacheText = ttsCacheKey(head.text);

    const ttsVoice = options.getVoice(head.voiceRole);
    const voiceHash = options.getVoiceHash({
      ttsBackend,
      ttsVoice,
      role: head.voiceRole,
      profileId: personalityProfileId,
    });
    const cachedUrl = options.getCache().get(cacheText, voiceHash);
    if (cachedUrl) {
      if (isExpiredAt(head.expiresAt)) {
        finish();
        return;
      }
      const radioMode = options.getRadioMode();
      if (options.shouldDiscard(radioMode)) {
        finish();
        return;
      }
      enqueueToAudioQueue(head, cachedUrl);
      if (!deferFinishUntilPlaybackIdle) {
        finish();
      }
      return;
    }

    const controller = new AbortController();
    abortController = controller;
    const timeoutId = setTimeout(() => controller.abort(), TTS_FETCH_TIMEOUT_MS);

    const queueItem = head;
    const ttsText = ttsCacheKey(queueItem.text);

    try {
      const blob = await options.fetchTts(ttsText, ttsVoice, controller.signal);
      if (!blob || blob.size === 0) throw new Error("TTS returned empty audio blob");

      const url = options.getCache().set(cacheText, voiceHash, blob);
      if (isExpiredAt(queueItem.expiresAt)) {
        finish();
        return;
      }
      const radioMode = options.getRadioMode();
      if (options.shouldDiscard(radioMode)) {
        console.log("[WS] TTS listo pero piloto activo — descartando reproducción");
        finish();
        return;
      }
      enqueueToAudioQueue(queueItem, url);
      if (!deferFinishUntilPlaybackIdle) {
        finish();
      }
    } catch (err) {
      if (controller.signal.aborted && !abortIntentional) {
        queue.unshift(queueItem);
      }
      if (controller.signal.aborted) {
        console.warn("[TTS] TTS timeout o cancelado");
      } else {
        console.warn("[TTS] TTS no disponible:", err);
      }
      finish();
    } finally {
      clearTimeout(timeoutId);
      if (abortController === controller) {
        abortController = null;
      }
    }
  }

  function enqueueToAudioQueue(item: TtsQueueItem, url: string): void {
    const aq = options.getAudioQueue?.() ?? audioQueue;
    const audioOpts = {
      expiresAt: item.expiresAt,
      delayedUntilMs: item.delayedUntilMs,
      validationKey: item.validationKey,
    };
    if (item.priority === "ENGINEER") {
      aq.enqueueEngineer(item.text, url, item.source, audioOpts);
    } else if (item.priority === "IMMEDIATE") {
      aq.enqueueImmediate(item.text, url, item.source, audioOpts);
    } else {
      aq.enqueue(item.text, url, "NORMAL" as SpotterTtsPriority, audioOpts);
    }
  }

  function finish(): void {
    clearWatchdog();
    clearDeferTimer();
    processing = false;
    currentPriority = null;
    options.onProcessingChange?.(false);
    void processNext();
  }

  function clearQueue(): void {
    queue.length = 0;
  }

  function clearQueueKeepImmediate(): void {
    for (let i = queue.length - 1; i >= 0; i -= 1) {
      if (queue[i].priority !== "IMMEDIATE") {
        queue.splice(i, 1);
      }
    }
  }

  function abortProcessingIntentional(): void {
    abortIntentional = true;
    abortController?.abort();
    abortController = null;
    processing = false;
    currentPriority = null;
    abortIntentional = false;
    clearWatchdog();
    clearDeferTimer();
    options.onProcessingChange?.(false);
  }

  function clearSpokenCooldown(): void {
    spokenAt.clear();
  }

  return {
    enqueue,
    processNext,
    finish,
    clearQueue,
    clearQueueKeepImmediate,
    clearSpokenCooldown,
    abortProcessingIntentional,
    getCurrentPriority: () => currentPriority,
    queueLength: () => queue.length,
    isProcessing: () => processing,
  };
}
