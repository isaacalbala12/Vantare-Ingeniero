/**
 * Cola de reproducción de audio TTS con prioridad CrewChief-style.
 * Soporta tanto la firma legacy enqueue(text, url) como la nueva enqueue(QueuedAudio).
 */
type PlaybackCallback = (isPlaying: boolean) => void;

interface QueuedAudio {
  text?: string;
  url?: string;
  audioFileId?: string;
  soundType: number;   // 0=SPOTTER, 1=CRITICAL, 2=IMPORTANT, 3=REGULAR
  priority: number;    // 20=CRITICAL, 15=HIGH, 10=MEDIUM, 5=LOW
  ttl: number;
  messageId: string;
  createdAt: number;
}

class AudioQueue {
  private queue: QueuedAudio[] = [];
  private current: QueuedAudio | null = null;
  private audio: HTMLAudioElement | null = null;
  private onPlaybackChange: PlaybackCallback | null = null;

  setOnPlaybackChange(cb: PlaybackCallback): void {
    this.onPlaybackChange = cb;
  }

  /** Legacy overload: text+url → construye QueuedAudio internamente. Compatible con App.tsx y TTS flow existente. */
  enqueue(text: string, url: string): void;
  /** New API: objeto tipado con prioridad para el sistema de colas del plan. */
  enqueue(msg: QueuedAudio): void;
  enqueue(textOrMsg: string | QueuedAudio, url?: string): void {
    let msg: QueuedAudio;
    if (typeof textOrMsg === 'string') {
      // Legacy call from App.tsx (text submit) / useWebSocket.ts (TTS flow)
      msg = {
        text: textOrMsg,
        url: url!,
        soundType: 3,     // REGULAR
        priority: 10,     // MEDIUM
        ttl: 15,
        messageId: (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}_${Math.random().toString(36).slice(2)}`),
        createdAt: Date.now(),
      };
    } else {
      msg = textOrMsg;
    }

    // Expiry check
    if (msg.ttl > 0 && (Date.now() - msg.createdAt) > msg.ttl * 1000) return;

    // Interrupt if higher priority spotter/critical
    if (this.current && msg.soundType <= 1 && this.current.soundType > msg.soundType) {
      this.stopCurrent();
    }

    // Insert by priority descending
    const idx = this.queue.findIndex(q => q.priority < msg.priority);
    idx === -1 ? this.queue.push(msg) : this.queue.splice(idx, 0, msg);

    if (!this.current) this.playNext();
  }

  private stopCurrent(): void {
    if (this.audio) {
      if (typeof this.audio.pause === "function") {
        this.audio.pause();
      }
      this.audio.src = "";
      this.audio = null;
    }
    this.current = null;
  }

  private async playNext(): Promise<void> {
    const now = Date.now();
    this.queue = this.queue.filter(m => !(m.ttl > 0 && (now - m.createdAt) > m.ttl * 1000));
    if (this.queue.length === 0) {
      this.current = null;
      if (this.onPlaybackChange) this.onPlaybackChange(false);
      return;
    }
    this.current = this.queue.shift()!;
    if (this.onPlaybackChange) this.onPlaybackChange(true);

    if (this.current.audioFileId) {
      const played = await this.tryPlayLocal(this.current.audioFileId);
      if (played) return;
    }
    if (this.current.url) await this.playUrl(this.current.url);
  }

  private tryPlayLocal(audioFileId: string): Promise<boolean> {
    return new Promise(resolve => {
      const audio = new Audio(`/audio/${audioFileId}.wav`);
      this.audio = audio;
      audio.onended = () => { resolve(true); this.playNext(); };
      audio.onerror = () => { resolve(false); this.playNext(); };
      audio.play().catch(() => { resolve(false); this.playNext(); });
    });
  }

  private playUrl(url: string): Promise<void> {
    return new Promise(resolve => {
      const audio = new Audio(url);
      this.audio = audio;
      audio.onended = () => { resolve(); this.playNext(); };
      audio.onerror = () => { resolve(); this.playNext(); };
      audio.play().catch(() => { resolve(); this.playNext(); });
    });
  }

  /** Alias legacy: stop() = clear() para compatibilidad con App.tsx */
  stop(): void { this.clear(); }
  clear(): void { this.stopCurrent(); this.queue = []; }
  get isPlaying(): boolean { return this.current !== null; }
}

export { AudioQueue };
export const audioQueue = new AudioQueue();
