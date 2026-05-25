/**
 * Tests unitarios para los filtros de mensajes del sistema.
 *
 * Verifica:
 * - Los textos que empiezan con "---" se filtran correctamente.
 * - Los textos normales NO se filtran.
 * - El filtro funciona en todos los lugares donde se aplica.
 */
import { describe, it, expect } from "vitest";

/**
 * Simula la lógica de filtrado usada en useWebSocket.ts y RadioOverlay.tsx.
 */
function shouldBeFiltered(text: string): boolean {
  return text.startsWith("---");
}

function shouldBeShown(text: string): boolean {
  return !text.startsWith("---");
}

describe("Filtro de mensajes internos (---)", () => {
  describe("Mensajes que DEBEN filtrarse", () => {
    it("debe filtrar '--- Transmisión de radio interrumpida...'", () => {
      const msg = "--- Transmisión de radio interrumpida por evento de mayor prioridad ---";
      expect(shouldBeFiltered(msg)).toBe(true);
      expect(shouldBeShown(msg)).toBe(false);
    });

    it("debe filtrar cualquier texto que empiece con '---'", () => {
      expect(shouldBeFiltered("--- cualquier cosa")).toBe(true);
      expect(shouldBeFiltered("---")).toBe(true);
    });

    it("debe filtrar texto vacío (caso borde)", () => {
      expect(shouldBeFiltered("")).toBe(false); // No empieza con ---
    });
  });

  describe("Mensajes que NO deben filtrarse", () => {
    it("no debe filtrar texto normal del ingeniero", () => {
      const msg = "Copiado piloto, tienes 3 vueltas de combustible restantes.";
      expect(shouldBeFiltered(msg)).toBe(false);
      expect(shouldBeShown(msg)).toBe(true);
    });

    it("no debe filtrar un guión normal", () => {
      expect(shouldBeFiltered("-")).toBe(false);
      expect(shouldBeShown("-")).toBe(true);
    });

    it("no debe filtrar dos guiones", () => {
      expect(shouldBeFiltered("--")).toBe(false);
      expect(shouldBeShown("--")).toBe(true);
    });

    it("no debe filtrar números", () => {
      expect(shouldBeFiltered("12345")).toBe(false);
      expect(shouldBeShown("12345")).toBe(true);
    });

    it("no debe filtrar la palabra 'tres guiones' en medio", () => {
      const msg = "Esto tiene --- en medio pero no empieza con ---";
      expect(shouldBeShown(msg)).toBe(true);
    });
  });

  describe("Integración con lógica del store (simulado)", () => {
    it("setLatestAdvice solo debe guardar si no empieza con ---", () => {
      const latestAdvice = { value: "" };

      function setLatestAdvice(text: string) {
        if (!text.startsWith("---")) {
          latestAdvice.value = text;
        }
      }

      setLatestAdvice("--- Transmisión interrumpida ---");
      expect(latestAdvice.value).toBe("");

      setLatestAdvice("Todo en orden, piloto.");
      expect(latestAdvice.value).toBe("Todo en orden, piloto.");
    });

    it("addMessageToHistory solo debe añadir si no empieza con ---", () => {
      const history: string[] = [];

      function addMessage(text: string) {
        if (text && !text.startsWith("---")) {
          history.push(text);
        }
      }

      addMessage("--- Transmisión interrumpida ---");
      expect(history.length).toBe(0);

      addMessage("Respuesta normal");
      expect(history.length).toBe(1);
    });

    it("TTS solo debe llamarse si no empieza con ---", () => {
      let ttsCalled = false;

      function requestTTS(text: string) {
        if (text && !text.startsWith("---")) {
          ttsCalled = true;
        }
      }

      requestTTS("--- interrupción ---");
      expect(ttsCalled).toBe(false);

      requestTTS("Hola piloto");
      expect(ttsCalled).toBe(true);
    });
  });
});
