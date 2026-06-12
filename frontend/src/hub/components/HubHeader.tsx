import { useAppStore } from "../../store/config";
import { t } from "../../i18n/strings";
import { StatusPill } from "./StatusPill";

interface HubHeaderProps {
  title: string;
  backendOk: boolean;
  lmuOk: boolean;
  llmOk: boolean;
}

export function HubHeader({ title, backendOk, lmuOk, llmOk }: HubHeaderProps) {
  const uiLanguage = useAppStore((s) => s.config.uiLanguage);

  return (
    <header className="h-14 border-b border-hub-border px-6 flex items-center justify-between bg-hub-surface/80">
      <h1
        className="text-base font-semibold tracking-wide text-a1-text"
        style={{ fontFamily: "var(--font-a1-display)" }}
      >
        {title}
      </h1>
      <div className="flex items-center gap-3 text-[10px] font-bold uppercase tracking-wider">
        <StatusPill label={t(uiLanguage, "connection")} ok={backendOk} />
        <StatusPill label="LMU" ok={lmuOk} />
        <StatusPill label="LLM" ok={llmOk} />
      </div>
    </header>
  );
}
