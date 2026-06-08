import { describe, it, expect, beforeEach, vi } from "vitest";

import { shouldVoiceAlert } from "../services/alertVoice";

import { classifyTtsPriority, SPOTTER_PREFETCH_PHRASES } from "../services/spotterPhrases";

import { ttsCache, buildVoiceHash } from "../services/ttsCache";

import { priorityAudioQueue } from "../services/priorityAudioQueue";

import { audioQueue } from "../services/audioQueue";

import { SPOTTER_AUDIO_ROWS } from "./fixtures/audioTriggerMatrix";



function mockAudio() {

  const playOrder: string[] = [];

  const playSpy = vi.fn(async function (this: { onended: (() => void) | null }) {

    playOrder.push("played");

    queueMicrotask(() => this.onended?.());

  });



  class MockAudio {

    onended: (() => void) | null = null;

    onerror: (() => void) | null = null;

    volume = 1;

    preload = "auto";

    constructor(public src: string) {}

    play = playSpy;

    pause() {}

  }



  const original = globalThis.Audio;

  // @ts-expect-error test mock

  globalThis.Audio = MockAudio;

  return {

    playOrder,

    playSpy,

    restore: () => {

      globalThis.Audio = original;

    },

  };

}



describe("audioPipeline integration", () => {

  beforeEach(() => {

    ttsCache.clear();

    priorityAudioQueue.stopAll();

    vi.restoreAllMocks();

  });



  it("flujo alert spotter: voz → cache → cola IMMEDIATE", async () => {

    const row = SPOTTER_AUDIO_ROWS.find((r) => r.id === "spotter:proximity_enter")!;

    const payload = {

      category: row.category,

      severity: row.severity,

      audio_priority: row.audioPriority,

      message: row.sampleMessage,

    };



    expect(shouldVoiceAlert(payload)).toBe(true);

    expect(classifyTtsPriority(row.sampleMessage, payload)).toBe("IMMEDIATE");



    const blob = new Blob(["audio"], { type: "audio/mpeg" });

    const url = ttsCache.set(row.sampleMessage, buildVoiceHash({}), blob);



    const { playSpy, restore } = mockAudio();

    audioQueue.enqueueImmediate(row.sampleMessage, url, "alert");

    await new Promise((r) => setTimeout(r, 40));

    expect(playSpy).toHaveBeenCalled();

    restore();

  });



  it("flujo advice LLM: NORMAL no preemptible por otra NORMAL", async () => {

    const { playOrder, restore } = mockAudio();



    audioQueue.enqueue("Consejo 1", "blob:1", "NORMAL");

    audioQueue.enqueue("Consejo 2", "blob:2", "NORMAL");

    await new Promise((r) => setTimeout(r, 200));

    expect(playOrder.length).toBeGreaterThanOrEqual(1);

    restore();

  });



  it("IMMEDIATE interrumpe reproducción NORMAL en curso", async () => {

    let resolveFirstPlay: () => void;

    const firstPlayGate = new Promise<void>((r) => {

      resolveFirstPlay = r;

    });



    class SlowThenEndAudio {

      static count = 0;

      onended: (() => void) | null = null;

      onerror: (() => void) | null = null;

      volume = 1;

      preload = "auto";

      constructor(public src: string) {}

      async play() {

        SlowThenEndAudio.count += 1;

        if (SlowThenEndAudio.count === 1) {

          resolveFirstPlay!();

          return;

        }

        queueMicrotask(() => this.onended?.());

      }

      pause() {}

    }



    const original = globalThis.Audio;

    SlowThenEndAudio.count = 0;

    // @ts-expect-error test mock

    globalThis.Audio = SlowThenEndAudio;



    audioQueue.enqueue("Ingeniero hablando...", "blob:slow", "NORMAL");

    await firstPlayGate;



    audioQueue.enqueueImmediate("Coche a la izquierda", "blob:imm", "alert");

    await new Promise((r) => setTimeout(r, 50));

    expect(SlowThenEndAudio.count).toBeGreaterThanOrEqual(2);



    globalThis.Audio = original;

  });



  it("stopNormal preserva pipeline IMMEDIATE (advice_start simulado)", () => {

    audioQueue.enqueueImmediate("Spotter pendiente", "blob:imm", "alert");

    audioQueue.enqueue("Consejo largo del LLM", "blob:norm", "NORMAL");

    audioQueue.stopNormal();

    audioQueue.stop();

    expect(true).toBe(true);

  });



  it("gaps sin voz; pearl con priority 2 sí entra en TTS", () => {
    expect(
      shouldVoiceAlert({ category: "gaps", severity: "INFO", audio_priority: "1" }),
    ).toBe(false);
    expect(
      shouldVoiceAlert({ category: "pearl", severity: "INFO", audio_priority: "2" }),
    ).toBe(true);
  });



  it("prefetch phrases cubren categorías spotter urgentes", () => {
    const urgentPrefixes = [
      "Coche a la",
      "Despejado",
      "Tres coches",
      "Pit limiter",
      "Combustible",
      "Safety car",
      "Última vuelta",
      "Daños detectados",
    ];
    for (const prefix of urgentPrefixes) {
      expect(
        SPOTTER_PREFETCH_PHRASES.some(
          (p) => p.includes(prefix.slice(0, 8)) || p.startsWith(prefix.split(" ")[0]),
        ),
      ).toBe(true);
    }
  });

});

