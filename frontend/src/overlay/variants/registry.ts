export type OverlayVariant = "a1" | "a2" | "a3";

export function getOverlayVariant(): OverlayVariant {
  const v = localStorage.getItem("overlayVariant");
  if (v === "a2" || v === "a3") return v;
  return "a1";
}
