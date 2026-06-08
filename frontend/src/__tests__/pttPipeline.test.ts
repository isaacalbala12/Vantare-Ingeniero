import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  PTT_EMPTY_MESSAGE,
  buildPttQuestionText,
  mergePttTranscripts,
  resolvePttQuestion,
  shouldTranscribeWav,
  transcribePttWav,
} from "../hub/pttPipeline";

describe("pttPipeline", () => {
  describe("mergePttTranscripts", () => {
    it("usa backend cuando SR está vacío", () => {
      expect(mergePttTranscripts("", "cuantas vueltas de combustible")).toBe(
        "cuantas vueltas de combustible",
      );
    });

    it("usa SR cuando backend está vacío", () => {
      expect(mergePttTranscripts("como va mi ritmo", "")).toBe("como va mi ritmo");
    });

    it("prefiere backend si tiene más palabras", () => {
      expect(
        mergePttTranscripts("combustible", "cuantas vueltas de combustible me quedan"),
      ).toBe("cuantas vueltas de combustible me quedan");
    });

    it("prefiere SR si tiene más palabras que backend ruidoso", () => {
      expect(
        mergePttTranscripts("como va mi ritmo en pista hoy", "como va"),
      ).toBe("como va mi ritmo en pista hoy");
    });
  });

  describe("shouldTranscribeWav", () => {
    it("rechaza blobs demasiado pequeños", () => {
      expect(shouldTranscribeWav(100)).toBe(false);
      expect(shouldTranscribeWav(512)).toBe(true);
    });
  });

  describe("resolvePttQuestion", () => {
    it("acepta pregunta válida", () => {
      const res = resolvePttQuestion("  como va mi ritmo?  ");
      expect(res).toEqual({ status: "ready", question: "como va mi ritmo?" });
    });

    it("rechaza texto vacío", () => {
      const res = resolvePttQuestion("  ");
      expect(res.status).toBe("empty");
      if (res.status === "empty") {
        expect(res.message).toBe(PTT_EMPTY_MESSAGE);
      }
    });
  });

  describe("transcribePttWav", () => {
    beforeEach(() => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => ({
          ok: true,
          json: async () => ({ text: "cuantas vueltas de combustible" }),
        })),
      );
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("llama /transcribe y devuelve texto", async () => {
      const blob = new Blob([new Uint8Array(600)], { type: "audio/wav" });
      const text = await transcribePttWav(blob, "http://127.0.0.1:8008");
      expect(text).toBe("cuantas vueltas de combustible");
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8008/transcribe",
        expect.objectContaining({ method: "POST" }),
      );
    });

    it("no llama API con wav pequeño", async () => {
      const blob = new Blob([new Uint8Array(10)], { type: "audio/wav" });
      const text = await transcribePttWav(blob, "http://127.0.0.1:8008");
      expect(text).toBe("");
      expect(fetch).not.toHaveBeenCalled();
    });
  });

  describe("buildPttQuestionText", () => {
    beforeEach(() => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => ({
          ok: true,
          json: async () => ({ text: "cuantas vueltas de combustible me quedan" }),
        })),
      );
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("combina SR + backend transcribe", async () => {
      const blob = new Blob([new Uint8Array(800)], { type: "audio/wav" });
      const q = await buildPttQuestionText("combustible", blob, "http://127.0.0.1:8008");
      expect(q).toBe("cuantas vueltas de combustible me quedan");
    });
  });
});
