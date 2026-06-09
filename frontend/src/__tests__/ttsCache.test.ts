import { describe, it, expect, beforeEach, vi } from "vitest";
import { ttsCache, buildVoiceHash } from "../services/ttsCache";

describe("ttsCache", () => {
  beforeEach(() => {
    ttsCache.clear();
    ttsCache.setMaxEntries(32);
  });

  it("devuelve null en miss", () => {
    expect(ttsCache.get("Hola", buildVoiceHash({}))).toBeNull();
  });

  it("guarda y recupera blob URL", () => {
    const blob = new Blob(["audio"], { type: "audio/mpeg" });
    const url = ttsCache.set("Coche a la derecha", buildVoiceHash({}), blob);
    expect(url.startsWith("blob:")).toBe(true);
    expect(ttsCache.get("Coche a la derecha", buildVoiceHash({}))).toBe(url);
  });

  it("normaliza espacios en la clave", () => {
    const blob = new Blob(["audio"], { type: "audio/mpeg" });
    ttsCache.set("  Hola   piloto ", buildVoiceHash({}), blob);
    expect(ttsCache.get("Hola piloto", buildVoiceHash({}))).not.toBeNull();
  });

  it("evict LRU cuando supera maxEntries", () => {
    ttsCache.setMaxEntries(2);
    ttsCache.set("a", "v", new Blob(["1"]));
    ttsCache.set("b", "v", new Blob(["2"]));
    ttsCache.set("c", "v", new Blob(["3"]));
    expect(ttsCache.size()).toBe(2);
    expect(ttsCache.get("a", "v")).toBeNull();
  });

  it("prefetch rellena cache", async () => {
    const fetchBlob = vi.fn(async (text: string) => new Blob([text], { type: "audio/mpeg" }));
    const count = await ttsCache.prefetch(["Coche a la izquierda", "Coche a la derecha"], "v", fetchBlob);
    expect(count).toBe(2);
    expect(fetchBlob).toHaveBeenCalledTimes(2);
    expect(ttsCache.get("Coche a la izquierda", "v")).not.toBeNull();
  });
});
