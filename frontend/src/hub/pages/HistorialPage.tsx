import { useEffect, useState } from "react";
import { HubCard } from "../components/HubCard";
import { getPlatform } from "../../core/platform";
import type { SessionHistoryFile } from "../../core/platform/types";

const SENDER_LABEL: Record<string, string> = {
  pilot: "Piloto",
  engineer: "Ingeniero",
  spotter: "Spotter",
};

export function HistorialPage() {
  const [files, setFiles] = useState<string[]>([]);
  const [selected, setSelected] = useState<SessionHistoryFile | null>(null);

  useEffect(() => {
    void getPlatform().listSessionHistories().then(setFiles);
  }, []);

  const loadFile = async (filename: string) => {
    const data = await getPlatform().loadSessionHistory(filename);
    setSelected(data);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
      <HubCard title="Sesiones">
        <div className="flex flex-col gap-2 max-h-[60vh] overflow-auto">
          {files.length === 0 ? (
            <p className="text-sm text-a1-text-muted">Sin historial guardado aún.</p>
          ) : (
            files.map((file) => (
              <button
                key={file}
                type="button"
                onClick={() => void loadFile(file)}
                className="text-left text-sm px-3 py-2 rounded-md border border-hub-border hover:border-a1-accent/40 hover:bg-white/5"
              >
                {file}
              </button>
            ))
          )}
        </div>
      </HubCard>
      <HubCard title="Mensajes">
        {!selected ? (
          <p className="text-sm text-a1-text-muted">Selecciona una sesión para ver el historial.</p>
        ) : (
          <div className="flex flex-col gap-3 max-h-[60vh] overflow-auto">
            {selected.messages.map((msg, idx) => (
              <div key={`${msg.timestamp}-${idx}`} className="text-sm border-b border-hub-border pb-2">
                <div className="text-[10px] uppercase tracking-wider text-a1-accent mb-1">
                  {SENDER_LABEL[msg.sender] ?? msg.sender}
                  {msg.category ? <span className="ml-2 text-[9px] text-a1-text-muted bg-hub-card px-1.5 py-0.5 rounded">{msg.category}</span> : null}
                </div>
                <div className="text-a1-text">{msg.text}</div>
              </div>
            ))}
          </div>
        )}
      </HubCard>
    </div>
  );
}
