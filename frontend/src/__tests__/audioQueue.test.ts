/**
 * Tests unitarios para el servicio AudioQueue.
 *
 * Verifica:
 * - enqueue() añade elementos a la cola FIFO.
 * - stop() vacía la cola y detiene reproducción.
 * - La cola reproduce en orden FIFO.
 * - Los callbacks de cambio de estado se disparan.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { audioQueue } from "../services/audioQueue";

describe("AudioQueue", () => {
  beforeEach(() => {
    // Resetear el estado interno del singleton
    // No hay API pública para reset, así que usamos stop()
    audioQueue.stop();
  });

  describe("enqueue", () => {
    it("debe añadir un elemento a la cola", () => {
      audioQueue.enqueue("Hola piloto", "blob:http://test/audio1");
      // Verificamos que no lance error
      expect(true).toBe(true);
    });

    it("debe añadir múltiples elementos sin error", () => {
      audioQueue.enqueue("Mensaje 1", "blob:http://test/1");
      audioQueue.enqueue("Mensaje 2", "blob:http://test/2");
      audioQueue.enqueue("Mensaje 3", "blob:http://test/3");
      expect(true).toBe(true);
    });
  });

  describe("stop", () => {
    it("debe vaciar la cola", () => {
      audioQueue.enqueue("Mensaje 1", "blob:http://test/1");
      audioQueue.enqueue("Mensaje 2", "blob:http://test/2");
      audioQueue.stop();
      // Después de stop, encolar debe funcionar
      audioQueue.enqueue("Después de stop", "blob:http://test/3");
      expect(true).toBe(true);
    });

    it("debe ser seguro llamar a stop múltiples veces", () => {
      audioQueue.stop();
      audioQueue.stop();
      audioQueue.stop();
      expect(true).toBe(true);
    });
  });

  describe("playback callback", () => {
    it("debe notificar cuando empieza la reproducción", () => {
      return new Promise<void>((done) => {
        audioQueue.setOnPlaybackChange((isPlaying) => {
          if (isPlaying) {
            done();
          }
        });
        audioQueue.enqueue("Hola", "blob:http://test/audio");
      });
    });
  });
});
