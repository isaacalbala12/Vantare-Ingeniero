/**
 * Cola FIFO de reproducción de audio TTS.
 * Evita que dos respuestas se pisen cuando llegan muy seguidas
 * (ej: trigger automático seguido de pregunta del piloto).
 */
import { invoke } from "@tauri-apps/api/core";

type PlaybackCallback = (isPlaying: boolean) => void;

async function setLmuDuck(active: boolean): Promise<void> {
  try {
    await invoke("duck_lmu", { active, level: 0.2 });
  } catch {
    // Graceful si no estamos en Tauri Windows o falla COM
  }
}

class AudioQueue {
  private queue: { text: string; url: string }[] = [];
  private playing = false;
  private onPlaybackChange: PlaybackCallback | null = null;

  /** Registra un callback para cambios de estado de reproducción. */
  setOnPlaybackChange(cb: PlaybackCallback): void {
    this.onPlaybackChange = cb;
  }

  /** Añade audio a la cola y comienza a reproducir si está inactiva. */
  enqueue(text: string, url: string): void {
    this.queue.push({ text, url });
    if (!this.playing) {
      this.playNext();
    }
  }

  /** Detiene la reproducción actual y vacía la cola. */
  stop(): void {
    this.queue = [];
    if (this.playing) {
      this.playing = false;
      void setLmuDuck(false);
      if (this.onPlaybackChange) this.onPlaybackChange(false);
    }
  }

  private playNext(): void {
    if (this.queue.length === 0) {
      this.playing = false;
      void setLmuDuck(false);
      if (this.onPlaybackChange) this.onPlaybackChange(false);
      return;
    }

    this.playing = true;
    if (this.onPlaybackChange) this.onPlaybackChange(true);
    void setLmuDuck(true);
    const task = this.queue.shift()!;
    const audio = new Audio(task.url);

    audio.onended = () => {
      URL.revokeObjectURL(task.url);
      this.playNext();
    };

    audio.onerror = () => {
      console.warn("[AudioQueue] Error reproduciendo audio, saltando al siguiente");
      URL.revokeObjectURL(task.url);
      this.playNext();
    };

    audio.play().catch((err) => {
      console.warn("[AudioQueue] Error al iniciar reproducción:", err);
      URL.revokeObjectURL(task.url);
      this.playNext();
    });
  }
}

export const audioQueue = new AudioQueue();
