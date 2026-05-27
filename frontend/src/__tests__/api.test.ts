import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock de useAppStore
vi.mock("../store/config", () => ({
  useAppStore: {
    getState: vi.fn(() => ({
      config: { vllmIP: "localhost", serverPort: 8008 },
      connectivity: { wsStatus: "DISCONNECTED" },
    })),
  },
}));

describe("API Service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getHealth", () => {
    it("debe devolver estructura correcta con respuesta OK", async () => {
      const mockResponse = {
        ok: true,
        json: async () => ({
          status: "ok",
          shared_memory: { status: "ok", offline_mode: true, last_lap: 0 },
          lmu_api: { status: "ok", cache: {} },
          llm: { configured: true, model: "test-model" },
        }),
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse));

      const { getHealth } = await import("../services/api");
      const result = await getHealth();

      expect(result.status).toBe("ok");
      expect(result.shared_memory).toBeDefined();
      expect(result.shared_memory.status).toBe("ok");
      expect(result.lmu_api).toBeDefined();
      expect(result.llm).toBeDefined();
      expect(result.llm.configured).toBe(true);
    });

    it("debe devolver status error con error HTTP", async () => {
      const mockResponse = {
        ok: true,
        json: async () => ({
          status: "error",
          shared_memory: { status: "offline", offline_mode: true, last_lap: 0 },
          lmu_api: { status: "idle", cache: {} },
          llm: { configured: false, model: "" },
        }),
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse));

      const { getHealth } = await import("../services/api");
      const result = await getHealth();

      expect(result.status).toBe("error");
      expect(result.websocket).toBe(false);
    });

    it("debe manejar respuesta sin campos opcionales", async () => {
      const mockResponse = {
        ok: true,
        json: async () => ({}),
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse));

      const { getHealth } = await import("../services/api");
      const result = await getHealth();

      expect(result.status).toBe("ok");
      expect(result.shared_memory.offline_mode).toBe(true);
      expect(result.llm.configured).toBe(false);
    });
  });

  describe("getHistory", () => {
    it("debe devolver array con registros", async () => {
      const mockRecords = [
        { lap: 1, consumption: 3.2, fuelRemaining: 97.0, lapTime: 92.5 },
        { lap: 2, consumption: 3.1, fuelRemaining: 93.9, lapTime: 91.8 },
      ];
      const mockResponse = {
        ok: true,
        json: async () => mockRecords,
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse));

      const { getHistory } = await import("../services/api");
      const result = await getHistory();

      expect(Array.isArray(result)).toBe(true);
      expect(result.length).toBe(2);
      expect(result[0].lap).toBe(1);
      expect(result[0].consumption).toBe(3.2);
    });

    it("debe devolver array vacío con error HTTP", async () => {
      const mockResponse = {
        ok: false,
        status: 404,
        statusText: "Not Found",
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse));

      const { getHistory } = await import("../services/api");
      const result = await getHistory();

      expect(Array.isArray(result)).toBe(true);
      expect(result.length).toBe(0);
    });

    it("debe devolver array vacío con respuesta vacía", async () => {
      const mockResponse = {
        ok: true,
        json: async () => [],
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse));

      const { getHistory } = await import("../services/api");
      const result = await getHistory();

      expect(Array.isArray(result)).toBe(true);
      expect(result.length).toBe(0);
    });

    it("debe devolver array vacío con excepción de red", async () => {
      vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network error")));

      const { getHistory } = await import("../services/api");
      const result = await getHistory();

      expect(Array.isArray(result)).toBe(true);
      expect(result.length).toBe(0);
    });
  });

  describe("URL construction", () => {
    it("debe usar localhost y puerto 8008 por defecto", async () => {
      const mockResponse = {
        ok: true,
        json: async () => ({ status: "ok" }),
      };
      const fetchMock = vi.fn().mockResolvedValue(mockResponse);
      vi.stubGlobal("fetch", fetchMock);

      const { getHealth } = await import("../services/api");
      await getHealth();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("localhost"),
        expect.any(Object)
      );
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("8008"),
        expect.any(Object)
      );
    });
  });
});
