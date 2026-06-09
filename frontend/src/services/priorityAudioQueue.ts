/**
 * Cola de reproducción: ENGINEER (LLM/PTT) > IMMEDIATE (spotter) > NORMAL.
 * El spotter no interrumpe voz del ingeniero; el ingeniero sí puede cortar spotter.
 */

import { getPlatform } from "../core/platform";
import { useAppStore } from "../store/config";
import { ensureAudioUnlocked } from "./audioUnlock";
import { volumePercentToAudioLevel } from "../hub/forms/volumeMigration";
import type { TtsPriority } from "./spotterPhrases";

type PlaybackCallback = (isPlaying: boolean, text?: string) => void;
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
    await getPlatform().duckLmu(active, DUCK_LEVEL);
  } catch {
    lmuDuckEngaged = !active;
  }
}

class PriorityAudioQueue {
  private engineerQueue: AudioItem[] = [];
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
    } else if (item.priority === "ENGINEER") {
      this.engineerQueue.push(item);
    } else {
      this.normalQueue.push(item);
    }
    this.schedulePlay();
  }

  enqueueEngineer(item: AudioItem): void {
    const engineerItem = { ...item, priority: "ENGINEER" as const, preemptible: false };
    if (this.playing && this.currentItem?.preemptible !== false) {
      this.interruptCurrent();
    }
    this.engineerQueue.push(engineerItem);
    this.schedulePlay();
  }

  enqueueImmediate(item: AudioItem): void {
    const immediateItem = {
      ...item,
      priority: "IMMEDIATE" as const,
      preemptible: item.preemptible ?? true,
    };
    if (this.playing && this.currentItem?.preemptible !== false) {
      this.interruptCurrent();
    }
    this.immediateQueue.unshift(immediateItem);
    this.schedulePlay();
  }

  stopAll(): void {
    this.engineerQueue = [];
    this.immediateQueue = [];
    this.normalQueue = [];
    this.interruptCurrent();
    this.notifyIdleIfIdle();
  }

  stopEngineer(): void {
    this.engineerQueue = [];
    this.normalQueue = [];
    if (
      this.playing &&
      this.currentItem &&
      (this.currentItem.priority === "ENGINEER" || this.currentItem.priority === "NORMAL")
    ) {
      this.interruptCurrent();
      void this.playNext();
    }
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
      preemptible: priority !== "ENGINEER",
      source,
      expiresAt: undefined,
      playEvenWhenSilenced: priority === "IMMEDIATE",
    };
    if (priority === "ENGINEER") {
      this.enqueueEngineer(item);
    } else if (priority === "IMMEDIATE") {
      this.enqueueImmediate(item);
    } else {
      this.enqueue(item);
    }
  }

  stop(): void {
    this.stopAll();
  }

  debugSnapshot(): { engineer: number; immediate: number; normal: number; playing: boolean } {
    return {
      engineer: this.engineerQueue.length,
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

    for (const queue of [this.engineerQueue, this.immediateQueue, this.normalQueue]) {
      while (queue.length > 0) {
        const next = queue.shift()!;
        if (this.isExpired(next)) {
          URL.revokeObjectURL(next.url);
          continue;
        }
        if (this.isDelayed(next)) {
          defer.push(next);
          continue;
        }
        this.requeueDeferred(defer);
        return next;
      }
    }

    this.requeueDeferred(defer);
    if (defer.length > 0) {
      const waitMs = Math.min(
        ...defer.map((item) => Math.max(0, (item.delayedUntilMs ?? Date.now()) - Date.now())),
        500,
      );
      window.setTimeout(() => this.schedulePlay(), waitMs);
    }
    return null;
  }

  private requeueDeferred(defer: AudioItem[]): void {
    for (const item of defer) {
      if (item.priority === "ENGINEER") this.engineerQueue.unshift(item);
      else if (item.priority === "IMMEDIATE") this.immediateQueue.unshift(item);
      else this.normalQueue.unshift(item);
    }
  }

  private notifyIdleIfIdle(): void {
    if (
      !this.playing &&
      this.engineerQueue.length === 0 &&
      this.immediateQueue.length === 0 &&
      this.normalQueue.length === 0
    ) {
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
    if (this.onPlaybackChange) this.onPlaybackChange(true, task.text);

    const audio = new Audio(task.url);
    const boost = useAppStore.getState().config.ttsVolumeBoost ?? 100;
    audio.volume = volumePercentToAudioLevel(boost);
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
      preemptible: priority !== "ENGINEER",
      source: "tts",
      expiresAt: options?.expiresAt,
      delayedUntilMs: options?.delayedUntilMs,
      validationKey: options?.validationKey,
      playEvenWhenSilenced: options?.playEvenWhenSilenced ?? priority === "IMMEDIATE",
    };
    if (priority === "ENGINEER") {
      priorityAudioQueue.enqueueEngineer(item);
    } else if (priority === "IMMEDIATE") {
      priorityAudioQueue.enqueueImmediate(item);
    } else {
      priorityAudioQueue.enqueue(item);
    }
  }

  enqueueEngineer(
    text: string,
    url: string,
    source = "advice",
    options?: {
      expiresAt?: number;
      delayedUntilMs?: number;
      validationKey?: string;
    },
  ): void {
    priorityAudioQueue.enqueueEngineer({
      text,
      url,
      priority: "ENGINEER",
      preemptible: false,
      source,
      expiresAt: options?.expiresAt,
      delayedUntilMs: options?.delayedUntilMs,
      validationKey: options?.validationKey,
      playEvenWhenSilenced: false,
    });
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
      preemptible: true,
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

  stopEngineer(): void {
    priorityAudioQueue.stopEngineer();
  }

  stopNormal(): void {
    priorityAudioQueue.stopNormal();
  }
}

export const audioQueue = new AudioQueueFacade();
