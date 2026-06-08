/** Cache LRU de blobs TTS → object URLs. */

import { normalizeTtsText } from "./spotterPhrases";

export interface TtsCacheKeyInput {
  text: string;
  voiceHash: string;
}

interface CacheEntry {
  url: string;
  lastUsed: number;
}

const DEFAULT_MAX = 32;

function cacheKey(text: string, voiceHash: string): string {
  return `${voiceHash}::${normalizeTtsText(text)}`;
}

class TtsCache {
  private entries = new Map<string, CacheEntry>();
  private maxEntries = DEFAULT_MAX;

  setMaxEntries(n: number): void {
    this.maxEntries = Math.max(1, n);
    this.evictIfNeeded();
  }

  get(text: string, voiceHash: string): string | null {
    const key = cacheKey(text, voiceHash);
    const entry = this.entries.get(key);
    if (!entry) return null;
    entry.lastUsed = Date.now();
    return entry.url;
  }

  set(text: string, voiceHash: string, blob: Blob): string {
    const key = cacheKey(text, voiceHash);
    const existing = this.entries.get(key);
    if (existing) {
      URL.revokeObjectURL(existing.url);
    }
    const url = URL.createObjectURL(blob);
    this.entries.set(key, { url, lastUsed: Date.now() });
    this.evictIfNeeded();
    return url;
  }

  evictIfNeeded(): void {
    while (this.entries.size > this.maxEntries) {
      let oldestKey: string | null = null;
      let oldest = Infinity;
      for (const [key, entry] of this.entries) {
        if (entry.lastUsed < oldest) {
          oldest = entry.lastUsed;
          oldestKey = key;
        }
      }
      if (!oldestKey) break;
      const removed = this.entries.get(oldestKey);
      if (removed) URL.revokeObjectURL(removed.url);
      this.entries.delete(oldestKey);
    }
  }

  clear(): void {
    for (const entry of this.entries.values()) {
      URL.revokeObjectURL(entry.url);
    }
    this.entries.clear();
  }

  size(): number {
    return this.entries.size;
  }

  async prefetch(
    texts: string[],
    voiceHash: string,
    fetchBlob: (text: string) => Promise<Blob | null>,
  ): Promise<number> {
    let hits = 0;
    for (const raw of texts) {
      const text = normalizeTtsText(raw);
      if (!text || this.get(text, voiceHash)) {
        hits += 1;
        continue;
      }
      const blob = await fetchBlob(text);
      if (blob && blob.size > 0) {
        this.set(text, voiceHash, blob);
        hits += 1;
      }
    }
    return hits;
  }
}

export const ttsCache = new TtsCache();

export function buildVoiceHash(config: {
  ttsBackend?: string;
  ttsVoice?: string;
  role?: "engineer" | "spotter";
  profileId?: string;
}): string {
  const backend = config.ttsBackend || "edge";
  const voice = config.ttsVoice || "default";
  const role = config.role || "engineer";
  const profile = config.profileId || "standard";
  return `${backend}:${voice}:${role}:${profile}`;
}
