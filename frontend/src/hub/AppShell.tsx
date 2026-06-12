import React, { useState } from "react";
import { HubSidebar } from "./components/HubSidebar";
import { HubHeader } from "./components/HubHeader";
import { type HubSection } from "./routes";
import { InicioPage } from "./pages/InicioPage";
import { HistorialPage } from "./pages/HistorialPage";
import ConfigTab from "../components/ConfigTab";
import { useAppStore } from "../store/config";
import { t } from "../i18n/strings";

interface AppShellProps {
  backendOk: boolean;
  lmuOk: boolean;
  llmOk: boolean;
}

const SECTION_TITLE_KEY: Record<HubSection, Parameters<typeof t>[1]> = {
  inicio: "home",
  ingeniero: "engineer",
  spotter: "spotter",
  audio: "audio",
  perfiles: "profiles",
  avanzado: "advanced",
  historial: "history",
};

function renderSection(section: HubSection): React.ReactNode {
  switch (section) {
    case "inicio":
      return <InicioPage />;
    case "ingeniero":
      return <ConfigTab section="ingeniero" />;
    case "spotter":
      return <ConfigTab section="spotter" />;
    case "audio":
      return <ConfigTab section="audio" />;
    case "perfiles":
      return <ConfigTab section="perfiles" />;
    case "avanzado":
      return <ConfigTab section="avanzado" />;
    case "historial":
      return <HistorialPage />;
    default:
      return <InicioPage />;
  }
}

export function AppShell({ backendOk, lmuOk, llmOk }: AppShellProps) {
  const [section, setSection] = useState<HubSection>("inicio");
  const uiLanguage = useAppStore((s) => s.config.uiLanguage);
  const title = t(uiLanguage, SECTION_TITLE_KEY[section]);

  return (
    <div className="hub-root w-screen h-screen flex overflow-hidden">
      <HubSidebar active={section} onNavigate={setSection} />
      <div className="flex-1 flex flex-col min-w-0">
        <HubHeader title={title} backendOk={backendOk} lmuOk={lmuOk} llmOk={llmOk} />
        <main className="flex-1 overflow-auto p-6 bg-a1-bg">
          <div className="max-w-6xl mx-auto">{renderSection(section)}</div>
        </main>
      </div>
    </div>
  );
}
