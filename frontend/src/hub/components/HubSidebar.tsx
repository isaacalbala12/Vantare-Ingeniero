import React from "react";
import {
  Bot,
  History,
  Home,
  Mic,
  Radio,
  SlidersHorizontal,
  UserCog,
} from "lucide-react";
import type { HubSection } from "../routes";

const ICONS: Record<HubSection, React.ReactNode> = {
  inicio: <Home size={18} />,
  ingeniero: <Bot size={18} />,
  spotter: <Radio size={18} />,
  audio: <Mic size={18} />,
  perfiles: <UserCog size={18} />,
  avanzado: <SlidersHorizontal size={18} />,
  historial: <History size={18} />,
};

interface HubSidebarProps {
  active: HubSection;
  onNavigate: (section: HubSection) => void;
  items: { id: HubSection; label: string }[];
}

export function HubSidebar({ active, onNavigate, items }: HubSidebarProps) {
  return (
    <aside className="w-[260px] shrink-0 bg-hub-sidebar border-r border-hub-border flex flex-col">
      <div className="px-6 py-5 border-b border-hub-border">
        <div
          className="text-lg font-bold tracking-[0.2em] uppercase text-a1-text"
          style={{ fontFamily: "var(--font-a1-display)" }}
        >
          Vantare
        </div>
        <div className="text-[10px] uppercase tracking-[0.35em] text-a1-accent mt-1">Ingeniero IA</div>
      </div>
      <nav className="flex-1 p-3 flex flex-col gap-1">
        {items.map((item) => {
          const isActive = item.id === active;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-a1-accent/15 text-a1-text border border-a1-accent/30"
                  : "text-a1-text-muted hover:text-a1-text hover:bg-white/5"
              }`}
            >
              <span className={isActive ? "text-a1-accent" : "text-a1-text-muted"}>{ICONS[item.id]}</span>
              {item.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
