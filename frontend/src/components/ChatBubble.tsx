import React from "react";

interface ChatBubbleProps {
  sender: "pilot" | "engineer" | "spotter";
  text: string;
}

/**
 * Burbuja de diálogo minimalista sin glassmorphism.
 * Fondo sólido #111, texto #fff, acento #8a2be2.
 */
export const ChatBubble: React.FC<ChatBubbleProps> = ({ sender, text }) => {
  const isEngineer = sender === "engineer";
  const isSpotter = sender === "spotter";
  const label = isEngineer ? "INGENIERO" : isSpotter ? "SPOTTER" : "PILOTO";

  return (
    <div className={`flex flex-col max-w-[85%] ${isEngineer || isSpotter ? "self-start" : "self-end"}`}>
      <span className={`text-[9px] font-bold tracking-wider mb-0.5 ${
        isEngineer ? "text-[#8a2be2]" : isSpotter ? "text-[#c9a227]" : "text-[#666]"
      }`}>
        {label}
      </span>
      <div className={`px-2.5 py-1.5 rounded text-xs leading-relaxed font-sans text-white select-text break-words ${
        isEngineer
          ? "bg-[#8a2be2]/20 border border-[#8a2be2]/40"
          : isSpotter
            ? "bg-[#c9a227]/15 border border-[#c9a227]/40"
          : "bg-[#222] border border-[#333]"
      }`}>
        {text}
      </div>
    </div>
  );
};

export default ChatBubble;
