import { useState } from "react";
import { CollapsibleSection } from "../components/CollapsibleSection";
import { getPlatform } from "../../core/platform";
import {
  RELEASE_PAGE_URL,
  useDesktopUpdate,
} from "../../services/desktopUpdate";
import { openReleaseUrl } from "../../services/updateChecker";

export function UpdatesPanel() {
  const { status, desktopAvailable, check, download, quitAndInstall, labelFor } =
    useDesktopUpdate();
  const [busy, setBusy] = useState(false);

  if (!desktopAvailable) {
    return (
      <CollapsibleSection title="Actualizaciones" defaultOpen>
        <p className="text-[12px] text-a1-text-muted leading-relaxed">
          Las actualizaciones automáticas están disponibles en la app de escritorio
          instalada. Descarga la última versión desde GitHub Releases.
        </p>
        <button
          type="button"
          className="hub-btn-secondary w-fit mt-2"
          onClick={() => openReleaseUrl(RELEASE_PAGE_URL)}
        >
          Abrir releases
        </button>
      </CollapsibleSection>
    );
  }

  const handleCheck = async () => {
    setBusy(true);
    try {
      await check();
    } finally {
      setBusy(false);
    }
  };

  const handleDownload = async () => {
    setBusy(true);
    try {
      await download();
    } finally {
      setBusy(false);
    }
  };

  const handleInstall = async () => {
    await quitAndInstall();
  };

  const showProgress =
    status.phase === "downloading" && typeof status.percent === "number";

  return (
    <CollapsibleSection title="Actualizaciones" defaultOpen>
      <div className="flex flex-col gap-3">
        <p className="text-[12px] text-a1-text-muted">
          Versión instalada: <span className="text-a1-text">v{status.currentVersion}</span>
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
          {(status.phase === "idle" ||
            status.phase === "not-available" ||
            status.phase === "error") && (
            <button
              type="button"
              className="hub-btn-primary"
              disabled={busy || status.phase === "checking"}
              onClick={() => void handleCheck()}
            >
              {status.phase === "checking" || busy ? "Comprobando…" : "Buscar actualizaciones"}
            </button>
          )}

          {status.phase === "available" && (
            <button
              type="button"
              className="hub-btn-primary"
              disabled={busy}
              onClick={() => void handleDownload()}
            >
              Descargar
            </button>
          )}

          {status.phase === "downloaded" && (
            <button type="button" className="hub-btn-primary" onClick={() => void handleInstall()}>
              Reiniciar para actualizar
            </button>
          )}

          <button
            type="button"
            className="hub-btn-secondary"
            onClick={() => getPlatform().openExternal(RELEASE_PAGE_URL)}
          >
            Abrir página de release
          </button>
        </div>
      </div>
    </CollapsibleSection>
  );
}
