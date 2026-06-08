/**
 * Cola de reproducción con prioridad IMMEDIATE (spotter) vs NORMAL (ingeniero).
 */

import { invoke } from "@tauri-apps/api/core";
import { useAppStore } from "../store/config";
import { ensureAudioUnlocked } from "./audioUnlock";
import type { TtsPriority } from "./spotterPhrases";

type PlaybackCallback = (isPlaying: boolean) => void;
type IdleCallback = () => void;

export interface AudioItem {
  text: string;
  url: string;
  priority: TtsPriority;
  preemptible: boolean;
  source: string;
  expiresAt?: number;
  delayedUntilMs?: number;
  validationKey?: string;
  playEvenWhenSilenced?: boolean;
}

let lmuDuckEngaged = false;
const DUCK_LMU_ENABLED = true;
const DUCK_LEVEL = 0.65;

async function setLmuDuck(active: boolean): Promise<void> {
  if (!DUCK_LMU_ENABLED) return;
  if (active === lmuDuckEngaged) return;
  lmuDuckEngaged = active;
  try {
    await invoke("duck_lmu", { active, level: DUCK_LEVEL });
  } catch {
    lmuDuckEngaged = !active;
  }
}

class PriorityAudioQueue {
  private immediateQueue: AudioItem[] = [];
  private normalQueue: AudioItem[] = [];
  private playing = false;
  private currentItem: AudioItem | null = null;
  private currentAudio: HTMLAudioElement | null = null;
  private onPlaybackChange: PlaybackCallback | null = null;
  private onIdle: IdleCallback | null = null;

  setOnPlaybackChange(cb: PlaybackCallback): void {
    this.onPlaybackChange = cb;
  }

  setOnIdle(cb: IdleCallback): void {
    this.onIdle = cb;
  }

  private schedulePlay(): void {
    if (this.playing) return;
    queueMicrotask(() => {
      if (!this.playing) {
        void this.playNext();
      }
    });
  }

  enqueue(item: AudioItem): void {
    if (item.priority === "IMMEDIATE") {
      this.immediateQueue.push(item);
    } else {
      this.normalQueue.push(item);
    }
    this.schedulePlay();
  }

  enqueueImmediate(item: AudioItem): void {
    const immediateItem = { ...item, priority: "IMMEDIATE" as const, preemptible: false };
    if (this.playing && this.currentItem?.priority === "NORMAL") {
      this.interruptCurrent();
    }
    this.immediateQueue.unshift(immediateItem);
    this.schedulePlay();
  }

  stopAll(): void {
    this.immediateQueue = [];
    this.normalQueue = [];
    this.interruptCurrent();
    this.notifyIdleIfIdle();
  }

  stopNormal(): void {
    this.normalQueue = [];
    if (this.playing && this.currentItem?.priority === "NORMAL") {
      this.interruptCurrent();
      void this.playNext();
    }
  }

  /** Compatibilidad con API anterior. */
  enqueueLegacy(text: string, url: string, priority: TtsPriority = "NORMAL", source = "legacy"): void {
    const item: AudioItem = {
      text,
      url,
      priority,
      preemptible: priority === "NORMAL",
      source,
      expiresAt: undefined,
      playEvenWhenSilenced: priority === "IMMEDIATE",
    };
    if (priority === "IMMEDIATE") {
      this.enqueueImmediate(item);
    } else {
      this.enqueue(item);
    }
  }

  stop(): void {
    this.stopAll();
  }

  debugSnapshot(): { immediate: number; normal: number; playing: boolean } {
    return {
      immediate: this.immediateQueue.length,
      normal: this.normalQueue.length,
      playing: this.playing,
    };
  }

  private isExpired(item: AudioItem): boolean {
    return typeof item.expiresAt === "number" && item.expiresAt <= Date.now();
  }

  private isDelayed(item: AudioItem): boolean {
    return typeof item.delayedUntilMs === "number" && item.delayedUntilMs > Date.now();
  }

  private interruptCurrent(): void {
    if (this.currentAudio) {
      this.currentAudio.onended = null;
      this.currentAudio.onerror = null;
      try {
        this.currentAudio.pause();
      } catch {
        /* jsdom Audio stub may lack pause */
      }
      if (this.currentItem) {
        URL.revokeObjectURL(this.currentItem.url);
      }
      this.currentAudio = null;
    }
    this.currentItem = null;
    this.playing = false;
    void setLmuDuck(false);
    if (this.onPlaybackChange) this.onPlaybackChange(false);
  }

  private pickNext(): AudioItem | null {
    const defer: AudioItem[] = [];

    while (this.immediateQueue.length > 0) {
      const next = this.immediateQueue.shift()!;
      if (this.isExpired(next)) {
        URL.revokeObjectURL(next.url);
        continue;
      }
      if (this.isDelayed(next)) {
        defer.push(next);
        continue;
      }
      this.immediateQueue.unshift(...defer);
      return next;
    }
    while (this.normalQueue.length > 0) {
      const next = this.normalQueue.shift()!;
      if (this.isExpired(next)) {
        URL.revokeObjectURL(next.url);
        continue;
      }
      if (this.isDelayed(next)) {
        defer.push(next);
        continue;
      }
      this.normalQueue.unshift(...defer);
      return next;
    }
    this.immediateQueue.unshift(...defer.filter((item) => item.priority === "IMMEDIATE"));
    this.normalQueue.unshift(...defer.filter((item) => item.priority === "NORMAL"));
    if (defer.length > 0) {
      const waitMs = Math.min(
        ...defer.map((item) => Math.max(0, (item.delayedUntilMs ?? Date.now()) - Date.now())),
        500,
      );
      window.setTimeout(() => this.schedulePlay(), waitMs);
    }
    return null;
  }

  private notifyIdleIfIdle(): void {
    if (!this.playing && this.immediateQueue.length === 0 && this.normalQueue.length === 0) {
      if (this.onIdle) this.onIdle();
    }
  }

  private async playNext(): Promise<void> {
    const task = this.pickNext();
    if (!task) {
      this.playing = false;
      void setLmuDuck(false);
      if (this.onPlaybackChange) this.onPlaybackChange(false);
      this.notifyIdleIfIdle();
      return;
    }

    this.playing = true;
    this.currentItem = task;
    if (this.onPlaybackChange) this.onPlaybackChange(true);

    const audio = new Audio(task.url);
    const boost = useAppStore.getState().config.ttsVolumeBoost ?? 1.0;
    audio.volume = Math.min(1, Math.max(0.1, boost));
    audio.preload = "auto";
    this.currentAudio = audio;

    try {
      await ensureAudioUnlocked();
      await audio.play();
      void setLmuDuck(true);
    } catch (err) {
      console.warn("[PriorityAudioQueue] Error al iniciar reproducción:", err);
      URL.revokeObjectURL(task.url);
      this.currentAudio = null;
      this.currentItem = null;
      void this.playNext();
      return;
    }

    audio.onended = () => {
      URL.revokeObjectURL(task.url);
      this.currentAudio = null;
      this.currentItem = null;
      void this.playNext();
    };

    audio.onerror = () => {
      console.warn("[PriorityAudioQueue] Error reproduciendo audio, saltando al siguiente");
      URL.revokeObjectURL(task.url);
      this.currentAudio = null;
      this.currentItem = null;
      void this.playNext();
    };
  }
}

export const priorityAudioQueue = new PriorityAudioQueue();

/** Singleton usado por el resto de la app (re-export con API legacy). */
class AudioQueueFacade {
  setOnPlaybackChange(cb: PlaybackCallback): void {
    priorityAudioQueue.setOnPlaybackChange(cb);
  }

  setOnIdle(cb: IdleCallback): void {
    priorityAudioQueue.setOnIdle(cb);
  }

  enqueue(
    text: string,
    url: string,
    priority: TtsPriority = "NORMAL",
    options?: {
      expiresAt?: number;
      delayedUntilMs?: number;
      validationKey?: string;
      playEvenWhenSilenced?: boolean;
    },
  ): void {
    const item: AudioItem = {
      text,
      url,
      priority,
      preemptible: priority === "NORMAL",
      source: "tts",
      expiresAt: options?.expiresAt,
      delayedUntilMs: options?.delayedUntilMs,
      validationKey: options?.validationKey,
      playEvenWhenSilenced: options?.playEvenWhenSilenced ?? priority === "IMMEDIATE",
    };
    if (priority === "IMMEDIATE") {
      priorityAudioQueue.enqueueImmediate(item);
    } else {
      priorityAudioQueue.enqueue(item);
    }
  }

  enqueueImmediate(
    text: string,
    url: string,
    source = "alert",
    options?: {
      expiresAt?: number;
      delayedUntilMs?: number;
      validationKey?: string;
      playEvenWhenSilenced?: boolean;
    },
  ): void {
    priorityAudioQueue.enqueueImmediate({
      text,
      url,
      priority: "IMMEDIATE",
      preemptible: false,
      source,
      expiresAt: options?.expiresAt,
      delayedUntilMs: options?.delayedUntilMs,
      validationKey: options?.validationKey,
      playEvenWhenSilenced: options?.playEvenWhenSilenced ?? true,
    });
  }

  stop(): void {
    priorityAudioQueue.stopAll();
  }

  stopNormal(): void {
    priorityAudioQueue.stopNormal();
  }
}

export const audioQueue = new AudioQueueFacade();
