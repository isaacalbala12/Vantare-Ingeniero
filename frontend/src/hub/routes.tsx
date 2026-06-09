export type HubSection =
  | "inicio"
  | "ingeniero"
  | "spotter"
  | "audio"
  | "perfiles"
  | "avanzado"
  | "historial";

export const HUB_SECTIONS: { id: HubSection; label: string }[] = [
  { id: "inicio", label: "Inicio" },
  { id: "ingeniero", label: "Ingeniero" },
  { id: "spotter", label: "Spotter" },
  { id: "audio", label: "Audio / PTT" },
  { id: "perfiles", label: "Perfiles" },
  { id: "avanzado", label: "Avanzado" },
  { id: "historial", label: "Historial" },
];
