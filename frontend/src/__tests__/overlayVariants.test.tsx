import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { A1ListeningChip } from "../overlay/variants/A1ListeningChip";
import { A1SpeakingCard } from "../overlay/variants/A1SpeakingCard";
import { useAppStore } from "../store/config";

describe("overlay variants", () => {
  it("listening chip shows escuchando label", () => {
    render(<A1ListeningChip />);
    expect(screen.getByText("Escuchando")).toBeTruthy();
    expect(screen.getByText("Vantare")).toBeTruthy();
  });

  it("speaking card shows engineer message", () => {
    useAppStore.setState({
      radio: {
        ...useAppStore.getState().radio,
        voicePlaybackText: "Entra a boxes esta vuelta.",
        mode: "SPEAKING_ENGINE",
      },
    });
    render(<A1SpeakingCard />);
    expect(screen.getByText("Entra a boxes esta vuelta.")).toBeTruthy();
    expect(screen.getByText("Hablando")).toBeTruthy();
  });
});
