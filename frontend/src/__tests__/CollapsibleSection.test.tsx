import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { CollapsibleSection } from "../hub/components/CollapsibleSection";

describe("CollapsibleSection", () => {
  it("oculta children hasta expandir", () => {
    render(
      <CollapsibleSection title="Voz TTS spotter">
        <p>Contenido spotter</p>
      </CollapsibleSection>,
    );
    // Initially hidden (collapsed by default)
    expect(screen.queryByText("Contenido spotter")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /voz tts spotter/i }));
    // Visible after click
    expect(screen.queryByText("Contenido spotter")).not.toBeNull();
  });
});
