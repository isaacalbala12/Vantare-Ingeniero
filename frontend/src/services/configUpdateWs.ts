import type { AppConfig } from "../store/config";
import { buildConfigUpdatePayload } from "./configUpdatePayload";

let activeWs: WebSocket | null = null;

export function registerConfigWs(ws: WebSocket | null): void {
  activeWs = ws;
}

export function sendConfigUpdate(cfg: AppConfig): void {
  if (activeWs?.readyState === WebSocket.OPEN) {
    activeWs.send(
      JSON.stringify({
        event: "config_update",
        data: buildConfigUpdatePayload(cfg),
      }),
    );
  }
}
