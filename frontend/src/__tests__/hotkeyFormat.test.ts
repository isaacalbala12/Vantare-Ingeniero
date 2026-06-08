import { describe, it, expect } from "vitest";
import {
  formatGamepadHotkeyLabel,
  gamepadButtonToHotkey,
  isGamepadHotkey,
  isMouseHotkey,
  keyboardEventToHotkey,
  normalizeHotkey,
  parseGamepadHotkey,
  toElectronAccelerator,
} from "../hub/forms/hotkeyFormat";

describe("hotkeyFormat", () => {
  it("normaliza Ctrl+Shift+Space", () => {
    expect(normalizeHotkey("ctrl+shift+space")).toBe("Ctrl+Shift+Space");
  });

  it("convierte a accelerator Electron", () => {
    expect(toElectronAccelerator("Ctrl+Shift+Space")).toBe("Control+Shift+Space");
    expect(toElectronAccelerator("Mouse4")).toBe("Mouse4");
  });

  it("detecta gamepad y ratón", () => {
    expect(isGamepadHotkey("Pad0:B12")).toBe(true);
    expect(isMouseHotkey("MouseBack")).toBe(true);
    expect(parseGamepadHotkey("Pad1:B3")).toEqual({ pad: 1, button: 3 });
    expect(gamepadButtonToHotkey(0, 7)).toBe("Pad0:B7");
    expect(formatGamepadHotkeyLabel("Pad0:B12")).toBe("Mando 1 · Botón 12");
  });

  it("ignora pulsación solo-modificador", () => {
    const event = {
      ctrlKey: true,
      shiftKey: false,
      altKey: false,
      metaKey: false,
      key: "Control",
    } as KeyboardEvent;
    expect(keyboardEventToHotkey(event)).toBeNull();
  });
});
