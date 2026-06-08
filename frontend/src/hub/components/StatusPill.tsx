interface StatusPillProps {
  label: string;
  ok: boolean;
}

export function StatusPill({ label, ok }: StatusPillProps) {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-hub-card border border-hub-border">
      <span className={`inline-block w-2 h-2 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`} />
      <span className="text-a1-text-muted">{label}</span>
    </div>
  );
}
