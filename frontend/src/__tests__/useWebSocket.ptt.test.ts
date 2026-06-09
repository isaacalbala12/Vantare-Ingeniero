import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

class MockWebSocket {
  public url: string;
  public readyState: number = WebSocket.OPEN;
  public onopen: ((event: unknown) => void) | null = null;
  public onmessage: ((event: { data: string }) => void) | null = null;
  public onclose: ((event: unknown) => void) | null = null;
  public onerror: ((event: unknown) => void) | null = null;
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    setTimeout(() => this.onopen?.({}), 0);
  }
  send(): void {}
  close(): void {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.({ code: 1000 });
  }
}

vi.stubGlobal("WebSocket", MockWebSocket);

vi.mock("../services/api", () => ({
  getHealth: vi.fn(async () => ({
    status: "ok",
    shared_memory: { status: "connected", offline_mode: true, last_lap: 0 },
    lmu_api: { status: "idle", cache: {} },
    llm: { configured: true, model: "test" },
    websocket: false,
  })),
}));

const mockStoreState = {
  config: {
    vllmIP: "localhost",
    serverPort: 8008,
    ttsVolumeBoost: 100,
    ttsBackend: "edge",
    ttsVoiceEngineer: "es-ES-AlvaroNeural",
    ttsVoiceSpotter: "es-ES-ElviraNeural",
    personalityProfileId: "default",
    speakOnlyWhenSpokenTo: false,
    spotterEnabled: true,
    engineerEnabled: true,
    brakingZonesMute: false,
  },
  setWsStatus: vi.fn(),
  setLatency: vi.fn(),
  updateTelemetry: vi.fn(),
  setRadioMode: vi.fn(),
  setCurrentTokens: vi.fn(),
  addMessageToHistory: vi.fn(),
  addRadioAlertToHistory: vi.fn(),
  setLatestAdvice: vi.fn(),
  setLatestAlert: vi.fn(),
  updateConfig: vi.fn(),
  radio: { mode: "THINKING_LLM", currentTokens: "", latestAdvice: "" },
  connectivity: { wsStatus: "DISCONNECTED" },
};

vi.mock("../store/config", () => ({
  useAppStore: Object.assign(() => mockStoreState, {
    subscribe: vi.fn(() => () => {}),
    getState: vi.fn(() => mockStoreState),
  }),
}));

vi.mock("../services/audioQueue", () => ({
  audioQueue: {
    enqueue: vi.fn(),
    enqueueEngineer: vi.fn(),
    enqueueImmediate: vi.fn(),
    stop: vi.fn(),
    stopEngineer: vi.fn(),
    stopNormal: vi.fn(),
    setOnPlaybackChange: vi.fn(),
    setOnIdle: vi.fn(),
  },
}));

vi.mock("../services/msgpack", () => ({
  encodeMsgpack: vi.fn(() => new Uint8Array()),
  decodeMsgpack: vi.fn(() => ({})),
  computeDelta: vi.fn(() => ({})),
  SNAPSHOT_INTERVAL: 100,
}));

vi.mock("../services/ttsCache", () => ({
  buildVoiceHash: vi.fn(() => "hash"),
  ttsCache: {
    get: vi.fn(() => "blob:cached"),
    set: vi.fn(() => "blob:test"),
    prefetch: vi.fn(async () => {}),
    clear: vi.fn(),
  },
}));

vi.mock("../services/configUpdateWs", () => ({ registerConfigWs: vi.fn() }));
vi.mock("../services/wsCommands", () => ({ registerWsCommands: vi.fn() }));

describe("useWebSocket PTT response flow", () => {
  let fakeNow = 0;

  beforeEach(() => {
    vi.clearAllMocks();
    fakeNow = 0;
    vi.spyOn(performance, "now").mockImplementation(() => fakeNow);
    mockStoreState.radio.mode = "THINKING_LLM";
    mockStoreState.radio.currentTokens = "";
  });

  it("advice_end con texto encola ENGINEER y limpia tokens", async () => {
    class TrackedMockWebSocket extends MockWebSocket {
      constructor(url: string) {
        super(url);
        (globalThis as { __lastWs?: MockWebSocket }).__lastWs = this;
      }
    }
    vi.stubGlobal("WebSocket", TrackedMockWebSocket);

    const { useWebSocket } = await import("../hooks/useWebSocket");
    const { audioQueue } = await import("../services/audioQueue");

    const { unmount } = renderHook(() => useWebSocket());
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const sock = (globalThis as { __lastWs?: MockWebSocket }).__lastWs;
    fakeNow = 20_000;
    await act(async () => {
      sock!.onmessage!({
        data: JSON.stringify({
          event: "advice_end",
          data: { full_text: "Tu ritmo es bueno, aguanta el stint." },
        }),
      });
      await new Promise((r) => setTimeout(r, 100));
    });

    expect(mockStoreState.setLatestAdvice).toHaveBeenCalledWith(
      "Tu ritmo es bueno, aguanta el stint.",
    );
    expect(mockStoreState.addMessageToHistory).toHaveBeenCalledWith(
      "engineer",
      "Tu ritmo es bueno, aguanta el stint.",
    );
    expect(audioQueue.enqueueEngineer).toHaveBeenCalled();
    unmount();
    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.unstubAllGlobals();
  });

  it("advice_end vacío muestra fallback", async () => {
    class TrackedMockWebSocket extends MockWebSocket {
      constructor(url: string) {
        super(url);
        (globalThis as { __lastWs?: MockWebSocket }).__lastWs = this;
      }
    }
    vi.stubGlobal("WebSocket", TrackedMockWebSocket);

    const { useWebSocket } = await import("../hooks/useWebSocket");
    const { unmount } = renderHook(() => useWebSocket());
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });

    const sock = (globalThis as { __lastWs?: MockWebSocket }).__lastWs;
    await act(async () => {
      sock!.onmessage!({
        data: JSON.stringify({ event: "advice_end", data: { full_text: "" } }),
      });
    });

    expect(mockStoreState.setLatestAdvice).toHaveBeenCalledWith(
      "No he recibido respuesta del ingeniero. Repite la pregunta.",
    );
    expect(mockStoreState.setRadioMode).toHaveBeenCalledWith("IDLE");
    unmount();
    vi.stubGlobal("WebSocket", MockWebSocket);
  });
});
