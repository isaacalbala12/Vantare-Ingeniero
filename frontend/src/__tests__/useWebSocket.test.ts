import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";

// Mock de WebSocket nativo
class MockWebSocket {
  public url: string;
  public readyState: number = WebSocket.OPEN;
  public onopen: ((event: any) => void) | null = null;
  public onmessage: ((event: any) => void) | null = null;
  public onclose: ((event: any) => void) | null = null;
  public onerror: ((event: any) => void) | null = null;

  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      if (this.onopen) this.onopen({});
    }, 0);
  }

  send(_data: any): void {}
  close(): void {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) this.onclose({ code: 1000, reason: "test" });
  }
}

// Reemplazar WebSocket global
vi.stubGlobal("WebSocket", MockWebSocket);

// Mock de audio queue
vi.mock("../services/audioQueue", () => ({
  audioQueue: {
    enqueue: vi.fn(),
    stop: vi.fn(),
    setOnPlaybackChange: vi.fn(),
  },
}));

// Mock de msgpack service
vi.mock("../services/msgpack", () => ({
  encodeMsgpack: vi.fn(() => new Uint8Array()),
  decodeMsgpack: vi.fn(() => ({})),
  computeDelta: vi.fn(() => ({})),
  SNAPSHOT_INTERVAL: 100,
}));

// Mock de useAppStore - debe tener .subscribe y .getState como propiedades del store
vi.mock("../store/config", () => {
  const mockStoreState = {
    config: { vllmIP: "localhost", serverPort: 8008 },
    setWsStatus: vi.fn(),
    setLatency: vi.fn(),
    updateTelemetry: vi.fn(),
    setRadioMode: vi.fn(),
    setCurrentTokens: vi.fn(),
    addMessageToHistory: vi.fn(),
    setLatestAdvice: vi.fn(),
    setLatestAlert: vi.fn(),
    radio: { mode: "IDLE", currentTokens: "" },
    connectivity: { wsStatus: "DISCONNECTED" },
  };

  const mockStore = Object.assign(
    () => mockStoreState,
    {
      subscribe: vi.fn(() => () => {}),
      getState: vi.fn(() => mockStoreState),
    }
  );

  return {
    useAppStore: mockStore,
  };
});

describe("useWebSocket", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("debe importarse sin errores", async () => {
    const { useWebSocket } = await import("../hooks/useWebSocket");
    expect(useWebSocket).toBeDefined();
    expect(typeof useWebSocket).toBe("function");
  });

  it("debe retornar disconnect como función", async () => {
    const { useWebSocket } = await import("../hooks/useWebSocket");
    const { result } = renderHook(() => useWebSocket());
    expect(typeof result.current.disconnect).toBe("function");
  });

  it("debe retornar sendJson como función", async () => {
    const { useWebSocket } = await import("../hooks/useWebSocket");
    const { result } = renderHook(() => useWebSocket());
    expect(typeof result.current.sendJson).toBe("function");
  });

  it("debe retornar sendBinary como función", async () => {
    const { useWebSocket } = await import("../hooks/useWebSocket");
    const { result } = renderHook(() => useWebSocket());
    expect(typeof result.current.sendBinary).toBe("function");
  });

  it("debe retornar connect como función", async () => {
    const { useWebSocket } = await import("../hooks/useWebSocket");
    const { result } = renderHook(() => useWebSocket());
    expect(typeof result.current.connect).toBe("function");
  });

  it("debe retornar estados null inicialmente", async () => {
    const { useWebSocket } = await import("../hooks/useWebSocket");
    const { result } = renderHook(() => useWebSocket());
    expect(result.current.lastTelemetry).toBeNull();
    expect(result.current.lastAdvice).toBeNull();
    expect(result.current.lastAlert).toBeNull();
    expect(result.current.lastPending).toBeNull();
    expect(result.current.lastStrategy).toBeNull();
  });

  it("sendJson debe retornar boolean", async () => {
    const { useWebSocket } = await import("../hooks/useWebSocket");
    const { result } = renderHook(() => useWebSocket());
    const retVal = result.current.sendJson("test_event", { data: "test" });
    expect(typeof retVal).toBe("boolean");
  });

  it("sendBinary debe retornar boolean", async () => {
    const { useWebSocket } = await import("../hooks/useWebSocket");
    const { result } = renderHook(() => useWebSocket());
    const retVal = result.current.sendBinary(new ArrayBuffer(10));
    expect(typeof retVal).toBe("boolean");
  });

  it("disconnect debe ejecutarse sin error", async () => {
    const { useWebSocket } = await import("../hooks/useWebSocket");
    const { result } = renderHook(() => useWebSocket());
    expect(() => result.current.disconnect()).not.toThrow();
  });
});
