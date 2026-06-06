import { describe, expect, it } from "vitest";
import { parseSpotterCommand } from "../services/spotterCommands";

describe("spotterCommands", () => {
  it("detecta activar spotter en español", () => {
    expect(parseSpotterCommand("espiar")).toBe("enable");
  });

  it("detecta desactivar spotter en español", () => {
    expect(parseSpotterCommand("deja de espiar")).toBe("disable");
  });

  it("detecta don't spot en inglés", () => {
    expect(parseSpotterCommand("don't spot")).toBe("disable");
  });

  it("devuelve null para frases normales", () => {
    expect(parseSpotterCommand("¿Cuánta gasolina me queda?")).toBeNull();
  });
});
