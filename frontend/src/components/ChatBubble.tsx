import React from "react";

interface ChatBubbleProps {
  sender: "pilot" | "engineer";
  text: string;
}

/**
 * Burbuja de diálogo minimalista sin glassmorphism.
 * Fondo sólido #111, texto #fff, acento #8a2be2.
 */
export const ChatBubble: React.FC<ChatBubbleProps> = ({ sender, text }) => {
  const isEngineer = sender === "engineer";

  return (
    <div className={`flex flex-col max-w-[85%] ${isEngineer ? "self-start" : "self-end"}`}>
      <span className={`text-[9px] font-bold tracking-wider mb-0.5 ${
        isEngineer ? "text-[#8a2be2]" : "text-[#666]"
      }`}>
        {isEngineer ? "INGENIERO" : "PILOTO"}
      </span>
      <div className={`px-2.5 py-1.5 rounded text-xs leading-relaxed font-sans text-white select-text break-words ${
        isEngineer 
          ? "bg-[#8a2be2]/20 border border-[#8a2be2]/40" 
          : "bg-[#222] border border-[#333]"
      }`}>
        {text}
      </div>
    </div>
  );
};

export default ChatBubble;
