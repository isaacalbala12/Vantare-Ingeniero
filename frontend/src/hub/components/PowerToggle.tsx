interface PowerToggleProps {
  label: string;
  description: string;
  enabled: boolean;
  disabled?: boolean;
  onToggle: () => void;
}

export function PowerToggle({
  label,
  description,
  enabled,
  disabled = false,
  onToggle,
}: PowerToggleProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onToggle}
      aria-pressed={enabled}
      className={[
        "w-full text-left rounded-lg border px-4 py-4 transition-colors",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        enabled
          ? "border-a1-accent/60 bg-a1-accent/10 hover:bg-a1-accent/15"
          : "border-hub-border bg-hub-card hover:bg-white/5",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-a1-text">{label}</div>
          <div className="text-xs text-a1-text-muted mt-1">{description}</div>
        </div>
        <div
          className={[
            "shrink-0 flex items-center gap-2 px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider",
            enabled ? "bg-a1-accent text-white" : "bg-hub-border text-a1-text-muted",
          ].join(" ")}
        >
          <span
            className={[
              "inline-block w-2 h-2 rounded-full",
              enabled ? "bg-white" : "bg-red-500",
            ].join(" ")}
          />
          {enabled ? "ON" : "OFF"}
        </div>
      </div>
    </button>
  );
}
