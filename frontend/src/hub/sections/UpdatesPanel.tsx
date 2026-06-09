import { useState } from "react";
import { CollapsibleSection } from "../components/CollapsibleSection";
import { useDesktopUpdate } from "../../services/desktopUpdate";

function primaryButtonLabel(
  busy: boolean,
  phase: string,
  percent?: number,
): string {
  if (busy || phase === "checking") return "Comprobando…";
  if (phase === "downloading") {
    return percent != null ? `Descargando… ${Math.round(percent)}%` : "Descargando…";
  }
  if (phase === "downloaded") return "Reiniciar para actualizar";
  return "Comprobar ahora";
}

export function UpdatesPanel() {
  const { status, desktopAvailable, updateNow, quitAndInstall, labelFor } =
    useDesktopUpdate();
  const [busy, setBusy] = useState(false);

  if (!desktopAvailable) {
    return (
      <CollapsibleSection title="Actualizaciones" defaultOpen>
        <p className="text-[12px] text-a1-text-muted leading-relaxed">
          Las actualizaciones automáticas solo están disponibles en la app de
          escritorio instalada (no en modo desarrollo).
        </p>
      </CollapsibleSection>
    );
  }

  const handlePrimary = async () => {
    if (status.phase === "downloaded") {
      await quitAndInstall();
      return;
    }
    setBusy(true);
    try {
      await updateNow();
    } finally {
      setBusy(false);
    }
  };

  const showProgress =
    status.phase === "downloading" && typeof status.percent === "number";
  const primaryDisabled =
    busy || status.phase === "checking" || status.phase === "downloading";

  return (
    <CollapsibleSection title="Actualizaciones" defaultOpen>
      <div className="flex flex-col gap-3">
        <p className="text-[12px] text-a1-text-muted">
          Versión instalada: <span className="text-a1-text">v{status.currentVersion}</span>
        </p>
        <p className="text-[12px] text-a1-text-muted leading-relaxed">
          Al abrir la app se busca una versión nueva y, si existe, se descarga e
          instala sola. Reinicia al terminar.
        </p>
        <p className="text-[12px] text-a1-text">{labelFor(status)}</p>

        {showProgress && (
          <div className="h-2 bg-[#222] rounded overflow-hidden w-full">
            <div
              className="h-full bg-a1-accent transition-none"
              style={{ width: `${Math.min(100, Math.max(0, status.percent ?? 0))}%` }}
            />
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="hub-btn-secondary"
            disabled={primaryDisabled}
            onClick={() => void handlePrimary()}
          >
            {primaryButtonLabel(busy, status.phase, status.percent)}
          </button>
        </div>
      </div>
    </CollapsibleSection>
  );
}
