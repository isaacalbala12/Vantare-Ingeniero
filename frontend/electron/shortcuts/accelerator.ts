/**
 * Convierte hotkey normalizado (Ctrl+Shift+Space) a accelerator Electron (Control+Shift+Space).
 * Duplicado inline para evitar cross-import de src/ en runtime Electron.
 */
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
