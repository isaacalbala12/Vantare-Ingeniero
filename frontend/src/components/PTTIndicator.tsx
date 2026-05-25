import React from "react";
import { useAppStore } from "../store/config";

/**
 * PTTIndicator simplificado para pruebas en el Dashboard.
 * Círculo sólido de 16px (w-4 h-4) sin animaciones.
 */
export const PTTIndicator: React.FC = () => {
  const mode = useAppStore((state) => state.radio.mode);

  let color = "#555"; // IDLE

  switch (mode) {
    case "LISTENING_PILOT":
      color = "#ff0000"; // Rojo
      break;
    case "THINKING_LLM":
      color = "#ffaa00"; // Ámbar
      break;
    case "SPEAKING_ENGINE":
      color = "#8a2be2"; // Púrpura
      break;
  }

  return (
    <div 
      className="w-4 h-4 rounded-full" 
      style={{ backgroundColor: color }}
      title={`Modo PTT: ${mode}`}
    />
  );
};

export default PTTIndicator;
