import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  buildUserOverrides,
  linesToTemplate,
  listSpotterKeys,
  templateToLines,
  type PhraseCatalog,
} from "../hub/sections/PhraseEditorPanel";

vi.mock("../store/config", () => ({
  useAppStore: {
    getState: vi.fn(() => ({
      config: { vllmIP: "127.0.0.1", serverPort: 8008 },
      connectivity: { wsStatus: "DISCONNECTED" },
    })),
  },
}));

const defaults: PhraseCatalog = {
  spotter: {
    standard: { clear_left: "Despejado izquierda|Izquierda libre" },
  },
  triggers: {
    fuel_critical: { standard: "Gasolina baja" },
  },
};

describe("PhraseEditor helpers", () => {
  it("convierte template pipe a líneas y viceversa", () => {
    expect(templateToLines("A|B|C")).toBe("A\nB\nC");
    expect(linesToTemplate("A\nB\nC")).toBe("A|B|C");
  });

  it("lista claves spotter del perfil", () => {
    expect(listSpotterKeys(defaults, "standard")).toEqual(["clear_left"]);
  });

  it("buildUserOverrides guarda solo delta respecto al bundle", () => {
    const merged: PhraseCatalog = {
      spotter: { standard: { clear_left: "Custom izquierda" } },
      triggers: {},
    };
    const user = buildUserOverrides(
      merged,
      defaults,
      "spotter",
      "standard",
      "clear_left",
      "Custom izquierda",
      { spotter: {}, triggers: {} },
    );
    expect(user.spotter.standard.clear_left).toBe("Custom izquierda");
  });

  it("buildUserOverrides elimina override si vuelve al default", () => {
    const user = buildUserOverrides(
      defaults,
      defaults,
      "spotter",
      "standard",
      "clear_left",
      "Despejado izquierda|Izquierda libre",
      {
        spotter: { standard: { clear_left: "Custom" } },
        triggers: {},
      },
    );
    expect(user.spotter.standard).toBeUndefined();
  });

  it("buildUserOverrides preserva overrides no editados", () => {
    const existing: PhraseCatalog = {
      spotter: { standard: { clear_left: "Custom A", clear_right: "Custom B" } },
      triggers: { fuel_critical: { standard: "Fuel custom" } },
    };
    const merged: PhraseCatalog = {
      spotter: { standard: { clear_left: "Custom A edit", clear_right: "Custom B" } },
      triggers: existing.triggers,
    };
    const user = buildUserOverrides(
      merged,
      defaults,
      "spotter",
      "standard",
      "clear_left",
      "Custom A edit",
      existing,
    );
    expect(user.spotter.standard.clear_left).toBe("Custom A edit");
    expect(user.spotter.standard.clear_right).toBe("Custom B");
    expect(user.triggers.fuel_critical.standard).toBe("Fuel custom");
  });
});

describe("Phrases API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it("savePhrases envía PUT con payload válido", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ saved: true }) });
    vi.stubGlobal("fetch", fetchMock);

    const { savePhrases } = await import("../services/api");
    const payload = { spotter: { standard: { clear_left: "Mi frase" } } };
    const result = await savePhrases(payload);

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8008/phrases",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    );
  });

  it("savePhrases devuelve detail en 422", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: "Perfil spotter inválido: bad" }),
      }),
    );

    const { savePhrases } = await import("../services/api");
    const result = await savePhrases({ spotter: { bad: { clear_left: "x" } } as any });

    expect(result.ok).toBe(false);
    expect(result.detail).toContain("inválido");
  });
});
