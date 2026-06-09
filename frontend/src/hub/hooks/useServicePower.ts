import { useCallback, useState } from "react";
import { useAppStore } from "../../store/config";
import { sendWsCommand } from "../../services/wsCommands";

export function useServicePower() {
  const spotterEnabled = useAppStore((s) => s.config.spotterEnabled);
  const engineerEnabled = useAppStore((s) => s.config.engineerEnabled);
  const wsConnected = useAppStore((s) => s.connectivity.wsStatus === "CONNECTED");
  const updateConfig = useAppStore((s) => s.updateConfig);
  const [syncError, setSyncError] = useState<string | null>(null);

  const applyToggle = useCallback(
    (
      key: "spotterEnabled" | "engineerEnabled",
      command: "spotter_command" | "engineer_command",
    ) => {
      const prev = useAppStore.getState().config[key];
      const next = !prev;
      updateConfig({ [key]: next });
      const ok = sendWsCommand(command, { action: next ? "enable" : "disable" });
      if (!ok) {
        updateConfig({ [key]: prev });
        setSyncError("No se pudo sincronizar con el backend. Revisa la conexión.");
        return;
      }
      setSyncError(null);
    },
    [updateConfig],
  );

  const toggleSpotter = useCallback(() => {
    applyToggle("spotterEnabled", "spotter_command");
  }, [applyToggle]);

  const toggleEngineer = useCallback(() => {
    applyToggle("engineerEnabled", "engineer_command");
  }, [applyToggle]);

  return {
    spotterEnabled,
    engineerEnabled,
    wsConnected,
    syncError,
    toggleSpotter,
    toggleEngineer,
  };
}
