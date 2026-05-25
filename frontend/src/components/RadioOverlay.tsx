import React from "react";
import { useAppStore } from "../store/config";
import PTTIndicator from "./PTTIndicator";
import ChatBubble from "./ChatBubble";

/**
 * Dashboard principal del Hub - Vista de telemetría y radio.
 * Fondo negro #111, texto blanco #fff, acento púrpura #8a2be2.
 */
export const Dashboard: React.FC = () => {
  // Selectores individuales para evitar re-renderizados completos a 20Hz
  const mode = useAppStore((s) => s.radio.mode);
  const currentTokens = useAppStore((s) => s.radio.currentTokens);
  const latestAdvice = useAppStore((s) => s.radio.latestAdvice);
  const messageHistory = useAppStore((s) => s.radio.messageHistory);
  const speed = useAppStore((s) => s.telemetry.speed ?? 0);
  const gear = useAppStore((s) => s.telemetry.gear ?? 0);
  const fuel = useAppStore((s) => s.telemetry.fuel ?? 0.0);
  const lap = useAppStore((s) => s.telemetry.lap ?? 1);
  const position = useAppStore((s) => s.telemetry.position ?? 1);
  const gapAhead = useAppStore((s) => s.telemetry.gaps?.ahead ?? 0.0);

  // Mapear modo radio a texto y color
  let modeText = "IDLE";
  let modeColor = "text-[#aaa]";

  switch (mode) {
    case "LISTENING_PILOT":
      modeText = "ESCUCHANDO";
      modeColor = "text-[#ff0000]";
      break;
    case "THINKING_LLM":
      modeText = "PENSANDO";
      modeColor = "text-[#ffaa00]";
      break;
    case "SPEAKING_ENGINE":
      modeText = "HABLANDO";
      modeColor = "text-[#8a2be2]";
      break;
  }

  const gearText = gear === 0 ? "N" : gear === -1 ? "R" : gear;
  const gapText = `+${gapAhead.toFixed(1)}s`;

  // Mensaje activo: streaming tokens o último consejo
  const lastHistoryMsg = messageHistory.length > 0 
    ? messageHistory[messageHistory.length - 1].text 
    : "";

  // Filtrar mensajes internos "---" que nunca deben mostrarse al usuario
  const safeAdvice = latestAdvice && !latestAdvice.startsWith("---") ? latestAdvice : "";
  const safeTokens = currentTokens && !currentTokens.startsWith("---") ? currentTokens : "";

  const activeMessageText = mode === "SPEAKING_ENGINE"
    ? (safeTokens || "Generando respuesta...")
    : (lastHistoryMsg || safeAdvice || "Radio silenciosa. Presiona PTT para transmitir.");

  // Últimos 3 mensajes del historial
  const lastMessages = messageHistory.slice(-3);

  return (
    <div 
      className="w-full h-full flex flex-col justify-between text-white select-none"
      style={{ fontFamily: "system-ui, sans-serif" }}
    >
      {/* Fila 1: Modo + Indicador PTT */}
      <div className="flex justify-between items-center px-3 py-2 border-b border-[#222]">
        <div className="flex items-center gap-2">
          <span className="font-bold text-[10px] text-[#aaa] tracking-wider">MODO:</span>
          <span className={`font-bold text-[14px] ${modeColor}`}>{modeText}</span>
        </div>
        <PTTIndicator />
      </div>

      {/* Fila 2: Último mensaje del ingeniero */}
      <div className="flex-1 px-3 py-2 flex flex-col justify-center min-h-0">
        <div className="text-[9px] uppercase font-bold text-[#8a2be2] tracking-wider mb-1">
          Último mensaje del ingeniero:
        </div>
        <div className="p-2 border border-[#8a2be2]/40 bg-[#1a1a1a] text-[13px] break-words overflow-y-auto max-h-[80px] rounded">
          {activeMessageText}
        </div>
      </div>

      {/* Fila 3: Telemetría básica (2 líneas) */}
      <div className="px-3 py-2 border-t border-b border-[#222] text-[12px] flex flex-col gap-1">
        <div>
          Vel: <span className="font-bold">{speed} km/h</span>
          &nbsp;|&nbsp;Marcha: <span className="font-bold text-[#8a2be2]">{gearText}</span>
          &nbsp;|&nbsp;Fuel: <span className="font-bold">{fuel.toFixed(1)}L</span>
        </div>
        <div>
          Vuelta: <span className="font-bold">{lap}</span>
          &nbsp;|&nbsp;Pos: <span className="font-bold">P{position}</span>
          &nbsp;|&nbsp;Gap: <span className="font-bold">{gapText}</span>
        </div>
      </div>

      {/* Fila 4: Historial (últimos 3 mensajes) */}
      <div className="px-3 py-2 text-[11px] flex flex-col gap-1 min-h-[50px] justify-end">
        <div className="text-[9px] uppercase font-bold text-[#555] tracking-wider mb-1">Historial:</div>
        {lastMessages.length === 0 ? (
          <div className="text-[#555] italic">Sin mensajes.</div>
        ) : (
          lastMessages.map((msg, index) => (
            <ChatBubble key={index} sender={msg.sender} text={msg.text} />
          ))
        )}
      </div>
    </div>
  );
};

export default Dashboard;
