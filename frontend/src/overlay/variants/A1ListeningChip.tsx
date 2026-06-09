import { memo } from "react";

export const A1ListeningChip = memo(function A1ListeningChip() {
  return (
    <div
      className="relative w-fit rounded-[5px] overflow-hidden shadow-[0_6px_24px_rgba(0,0,0,0.55)] bg-[#121216] border border-[rgba(237,237,240,0.08)]"
      style={{ fontFamily: "var(--font-a1-body)", contain: "layout style paint" }}
    >
      <div
        className="overlay-a1-stripe absolute top-2 bottom-2 left-2.5 w-[3px] rounded-sm opacity-70"
        style={{ background: "linear-gradient(180deg, transparent, #c42040, #9b1b32, #c42040, transparent)" }}
      />
      <div className="relative z-10 flex items-center gap-3 px-4 py-2.5 pl-6 whitespace-nowrap">
        <div
          className="text-[13px] font-bold tracking-[0.12em] uppercase text-[#ededf0]"
          style={{ fontFamily: "var(--font-a1-display)" }}
        >
          Vantare
        </div>
        <div className="text-[10px] font-semibold tracking-[0.35em] uppercase text-[#c42040]">Escuchando</div>
        <div className="overlay-a1-live-dot flex items-center gap-1.5 text-[9px] font-semibold tracking-[0.15em] uppercase text-[#c42040]">
          <span className="inline-block w-[5px] h-[5px] rounded-full bg-[#c42040]" />
          Mic
        </div>
      </div>
    </div>
  );
});
