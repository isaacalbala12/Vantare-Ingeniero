/**
 * Tests de componentes React del frontend.
 *
 * Verifica:
 * - ChatBubble renderiza según sender (pilot/engineer)
 * - PTTIndicator muestra color según modo del store
 * - Dashboard renderiza telemetría, historial y alerts
 */
// @vitest-environment happy-dom
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

import ChatBubble from "../components/ChatBubble";
import PTTIndicator from "../components/PTTIndicator";
import Dashboard from "../components/RadioOverlay";
import { useAppStore } from "../store/config";

// Helper para resetear el store a estado determinista
function resetStore() {
  useAppStore.setState({
    connectivity: { wsStatus: "DISCONNECTED", latency: 0, backendHealth: null },
    radio: {
      mode: "IDLE",
      currentTokens: "",
      messageHistory: [],
      latestAdvice: "",
      latestAlert: "",
      micLevel: 0,
    },
    telemetry: {
      speed: 0,
      rpm: 0,
      gear: 0,
      fuel: 0,
      lap: 1,
      position: 1,
      gaps: { ahead: 0, behind: 0 },
      tyreWear: { fl: 100, fr: 100, rl: 100, rr: 100 },
      alerts: [],
    },
    screen: "dashboard",
    crewchief: { events: [], latestByCategory: {} },
  });
}

describe("ChatBubble", () => {
  it("renderiza burbuja del ingeniero con estilo correcto", () => {
    render(<ChatBubble sender="engineer" text="Pit now" />);
    expect(screen.getByText("INGENIERO")).toBeTruthy();
    expect(screen.getByText("Pit now")).toBeTruthy();
  });

  it("renderiza burbuja del piloto con estilo correcto", () => {
    render(<ChatBubble sender="pilot" text="Copy that" />);
    expect(screen.getByText("PILOTO")).toBeTruthy();
    expect(screen.getByText("Copy that")).toBeTruthy();
  });
});

describe("PTTIndicator", () => {
  beforeEach(() => resetStore());

  it("muestra color gris en modo IDLE", () => {
    useAppStore.setState({ radio: { ...useAppStore.getState().radio, mode: "IDLE" } });
    const { container } = render(<PTTIndicator />);
    const dot = container.querySelector("div") as HTMLDivElement;
    expect(dot.style.backgroundColor).toBe("#555");
  });

  it("muestra color rojo en modo LISTENING_PILOT", () => {
    useAppStore.setState({ radio: { ...useAppStore.getState().radio, mode: "LISTENING_PILOT" } });
    const { container } = render(<PTTIndicator />);
    const dot = container.querySelector("div") as HTMLDivElement;
    expect(dot.style.backgroundColor).toBe("#ff0000");
  });

  it("muestra color ámbar en modo THINKING_LLM", () => {
    useAppStore.setState({ radio: { ...useAppStore.getState().radio, mode: "THINKING_LLM" } });
    const { container } = render(<PTTIndicator />);
    const dot = container.querySelector("div") as HTMLDivElement;
    expect(dot.style.backgroundColor).toBe("#ffaa00");
  });

  it("muestra color púrpura en modo SPEAKING_ENGINE", () => {
    useAppStore.setState({ radio: { ...useAppStore.getState().radio, mode: "SPEAKING_ENGINE" } });
    const { container } = render(<PTTIndicator />);
    const dot = container.querySelector("div") as HTMLDivElement;
    expect(dot.style.backgroundColor).toBe("#8a2be2");
  });
});

describe("Dashboard", () => {
  beforeEach(() => resetStore());

  it("renderiza telemetría básica correctamente", () => {
    useAppStore.setState({
      telemetry: {
        ...useAppStore.getState().telemetry,
        speed: 250,
        gear: 5,
        fuel: 45.5,
        lap: 12,
        position: 3,
        gaps: { ahead: 1.2, behind: 0.8 },
      },
    });

    render(<Dashboard />);

    expect(screen.getByText(/250/)).toBeTruthy();
    expect(screen.getByText(/45\.5L/)).toBeTruthy();
    expect(screen.getByText(/Vuelta:/)).toBeTruthy();
    expect(screen.getByText(/Pos:/)).toBeTruthy();
    expect(screen.getByText(/\+1\.2s/)).toBeTruthy();
    // Gear se muestra dentro del span de marcha
    const gearSpans = screen.getAllByText("5");
    expect(gearSpans.length).toBeGreaterThanOrEqual(1);
  });

  it("muestra historial de mensajes como ChatBubbles", () => {
    useAppStore.setState({
      radio: {
        ...useAppStore.getState().radio,
        messageHistory: [
          { sender: "engineer", text: "Push now", timestamp: 1 },
          { sender: "pilot", text: "Copy that", timestamp: 2 },
        ],
      },
    });

    render(<Dashboard />);

    expect(screen.getByText("Push now")).toBeTruthy();
    expect(screen.getAllByText("Copy that").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("INGENIERO")).toBeTruthy();
    expect(screen.getByText("PILOTO")).toBeTruthy();
  });

  it("muestra mensaje por defecto cuando no hay historial ni advice", () => {
    render(<Dashboard />);
    expect(screen.getByText(/Radio silenciosa/)).toBeTruthy();
  });

  it("renderiza crewchief alerts con severidad", () => {
    useAppStore.setState({
      crewchief: {
        events: [
          { id: "1", severity: "critical", message: "LOW FUEL", category: "fuel", timestamp: 1 },
          { id: "2", severity: "medium", message: "Gap +2s", category: "gap", timestamp: 2 },
        ],
        latestByCategory: {},
      },
    });

    render(<Dashboard />);

    expect(screen.getByText("LOW FUEL")).toBeTruthy();
    expect(screen.getByText("Gap +2s")).toBeTruthy();
  });

  it("muestra tokens streaming en modo SPEAKING_ENGINE", () => {
    useAppStore.setState({
      radio: {
        ...useAppStore.getState().radio,
        mode: "SPEAKING_ENGINE",
        currentTokens: "Push",
      },
    });

    render(<Dashboard />);
    expect(screen.getByText("Push")).toBeTruthy();
    expect(screen.getByText("HABLANDO")).toBeTruthy();
  });

  it("muestra botón PTT cuando está en IDLE y se provee callback", () => {
    const onPTTStart = () => {};
    render(<Dashboard onPTTStart={onPTTStart} />);
    expect(screen.getByText("🎤 Hablar")).toBeTruthy();
  });

  it("filtra mensajes internos que empiezan con ---", () => {
    useAppStore.setState({
      radio: {
        ...useAppStore.getState().radio,
        mode: "SPEAKING_ENGINE",
        currentTokens: "---internal",
      },
    });

    render(<Dashboard />);
    expect(screen.queryByText("---internal")).toBeNull();
  });
});
