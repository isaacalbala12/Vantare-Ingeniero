const MOD_MAP: Record<string, string> = {
  control: "Ctrl",
  ctrl: "Ctrl",
  shift: "Shift",
  alt: "Alt",
  meta: "Win",
  super: "Win",
  win: "Win",
  cmd: "Win",
};

const MOUSE_LABELS: Record<number, string> = {
  0: "MouseLeft",
  1: "MouseMiddle",
  2: "MouseRight",
  3: "MouseBack",
  4: "MouseForward",
  5: "Mouse5",
};

const MOUSE_BY_LABEL: Record<string, number> = Object.fromEntries(
  Object.entries(MOUSE_LABELS).map(([code, label]) => [label, Number(code)]),
);

export type GamepadHotkey = { pad: number; button: number };

export function isMouseHotkey(raw: string): boolean {
  return raw.startsWith("Mouse");
}

export function isGamepadHotkey(raw: string): boolean {
  return /^Pad\d+:B\d+$/i.test(raw.trim());
}

export function gamepadButtonToHotkey(padIndex: number, buttonIndex: number): string {
  return `Pad${padIndex}:B${buttonIndex}`;
}

export function parseGamepadHotkey(raw: string): GamepadHotkey | null {
  const match = raw.trim().match(/^Pad(\d+):B(\d+)$/i);
  if (!match) return null;
  return { pad: Number(match[1]), button: Number(match[2]) };
}

export function formatGamepadHotkeyLabel(raw: string): string {
  const parsed = parseGamepadHotkey(raw);
  if (!parsed) return raw;
  return `Mando ${parsed.pad + 1} · Botón ${parsed.button}`;
}

export function mouseHotkeyToButton(raw: string): number | null {
  const label = raw.trim();
  return MOUSE_BY_LABEL[label] ?? null;
}

export function normalizeHotkey(raw: string): string {
  const parts = raw.split("+").map((p) => p.trim()).filter(Boolean);
  return parts
    .map((p) => {
      const lower = p.toLowerCase();
      if (MOD_MAP[lower]) return MOD_MAP[lower];
      if (lower.length === 1) return lower.toUpperCase();
      if (lower.startsWith("mouse")) return p;
      return p.length <= 3 ? p.toUpperCase() : p.charAt(0).toUpperCase() + p.slice(1);
    })
    .join("+");
}

const MODIFIERS = new Set(["Ctrl", "Shift", "Alt", "Win"]);

export function keyboardEventToHotkey(e: KeyboardEvent): string | null {
  const parts: string[] = [];
  if (e.ctrlKey) parts.push("Ctrl");
  if (e.shiftKey) parts.push("Shift");
  if (e.altKey) parts.push("Alt");
  if (e.metaKey) parts.push("Win");
  const key = e.key;
  if (!["Control", "Shift", "Alt", "Meta"].includes(key)) {
    parts.push(key === " " ? "Space" : key.length === 1 ? key.toUpperCase() : key);
  }
  if (!parts.some((p) => !MODIFIERS.has(p))) {
    return null;
  }
  return normalizeHotkey(parts.join("+"));
}

export function mouseButtonToHotkey(button: number): string | null {
  const label = MOUSE_LABELS[button];
  return label ?? null;
}

export function toElectronAccelerator(combo: string): string {
  return combo
    .split("+")
    .map((p) => {
      if (p === "Ctrl") return "Control";
      if (p === "Win") return "Super";
      return p;
    })
    .join("+");
}
