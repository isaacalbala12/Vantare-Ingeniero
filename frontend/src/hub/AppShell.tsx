import React, { useState } from "react";
import { HubSidebar } from "./components/HubSidebar";
import { HubHeader } from "./components/HubHeader";
import { HUB_SECTIONS, type HubSection } from "./routes";
import { InicioPage } from "./pages/InicioPage";
import { HistorialPage } from "./pages/HistorialPage";
import ConfigTab from "../components/ConfigTab";

interface AppShellProps {
  backendOk: boolean;
  lmuOk: boolean;
  llmOk: boolean;
}

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
  const title = HUB_SECTIONS.find((s) => s.id === section)?.label ?? "Inicio";

  return (
    <div className="hub-root w-screen h-screen flex overflow-hidden">
      <HubSidebar active={section} onNavigate={setSection} items={HUB_SECTIONS} />
      <div className="flex-1 flex flex-col min-w-0">
        <HubHeader title={title} backendOk={backendOk} lmuOk={lmuOk} llmOk={llmOk} />
        <main className="flex-1 overflow-auto p-6 bg-a1-bg">
          <div className="max-w-6xl mx-auto">{renderSection(section)}</div>
        </main>
      </div>
    </div>
  );
}
