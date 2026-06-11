import { useAppStore } from "../store/config";

export interface HealthResponse {
  status: string;
  shared_memory: {
    status: string;
    offline_mode: boolean;
    last_lap: number;
  };
  lmu_api: {
    status: string;
    cache?: any;
  };
  llm: {
    configured: boolean;
    model?: string;
  };
  websocket?: boolean;
}

export interface ConsumptionRecord {
  lap: number;
  consumption: number;
  fuelRemaining: number;
  lapTime: number;
}

const getBaseUrl = () => {
  const { config } = useAppStore.getState();
  const vllmIP = config.vllmIP || "127.0.0.1";
  const serverPort = config.serverPort || 8008;
  return `http://${vllmIP}:${serverPort}`;
};

/**
 * Consulta el estado de salud del backend asíncrono
 */
/** null = backend inalcanzable (no confundir con «ok»). */
export async function getHealth(): Promise<HealthResponse | null> {
  const url = `${getBaseUrl()}/health`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) {
      console.warn("[api] Health HTTP", res.status);
      return null;
    }
    const data = await res.json();
    if ((data.status ?? "ok") !== "ok") {
      console.warn("[api] Health status not ok:", data.status);
      return null;
    }
    return {
      status: "ok",
      shared_memory: {
        status: data.shared_memory?.status || "offline",
        offline_mode: data.shared_memory?.offline_mode ?? true,
        last_lap: data.shared_memory?.last_lap ?? 0,
      },
      lmu_api: {
        status: data.lmu_api?.status || "idle",
        cache: data.lmu_api?.cache || {},
      },
      llm: {
        configured: data.llm?.configured ?? false,
        model: data.llm?.model || "",
      },
      websocket: useAppStore.getState().connectivity.wsStatus === "CONNECTED",
    };
  } catch (err) {
    console.warn("[api] Backend unreachable:", err);
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Recupera el registro histórico de consumo de combustible
 */
export async function getHistory(): Promise<ConsumptionRecord[]> {
  const url = `${getBaseUrl()}/history`;
  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.warn("[api] History endpoint returned", res.status);
      return [];
    }
    return await res.json();
  } catch (err) {
    console.warn("[api] Error fetching history:", err);
    return [];
  }
}

export interface VersionInfo {
  version: string;
  backend: string;
  github_repo: string;
}

export interface UpdateCheckResult {
  current_version: string;
  latest_version: string;
  update_available: boolean;
  release_url: string;
  release_name?: string;
}

export async function getVersion(): Promise<VersionInfo | null> {
  try {
    const res = await fetch(`${getBaseUrl()}/version`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function checkForUpdate(): Promise<UpdateCheckResult | null> {
  try {
    const res = await fetch(`${getBaseUrl()}/version/check`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function listProfiles(): Promise<string[]> {
  try {
    const res = await fetch(`${getBaseUrl()}/profiles`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.profiles ?? [];
  } catch {
    return [];
  }
}

export async function loadProfile(name: string): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${getBaseUrl()}/profiles/${encodeURIComponent(name)}`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.config ?? null;
  } catch {
    return null;
  }
}

export async function saveProfile(name: string, config: Record<string, unknown>): Promise<boolean> {
  try {
    const res = await fetch(`${getBaseUrl()}/profiles/${encodeURIComponent(name)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function deleteProfile(name: string): Promise<boolean> {
  try {
    const res = await fetch(`${getBaseUrl()}/profiles/${encodeURIComponent(name)}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export interface PhraseCatalog {
  spotter: Record<string, Record<string, string>>;
  triggers: Record<string, Record<string, string>>;
}

export async function getPhrasesMerged(): Promise<PhraseCatalog | null> {
  try {
    const res = await fetch(`${getBaseUrl()}/phrases`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function getPhrasesDefaults(): Promise<PhraseCatalog | null> {
  try {
    const res = await fetch(`${getBaseUrl()}/phrases/defaults`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function exportPhrases(): Promise<PhraseCatalog | null> {
  try {
    const res = await fetch(`${getBaseUrl()}/phrases/export`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function getPhrasesMeta(): Promise<{ user_load_error: string | null } | null> {
  try {
    const res = await fetch(`${getBaseUrl()}/phrases/meta`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function savePhrases(
  payload: Partial<PhraseCatalog>,
  options?: { replace?: boolean },
): Promise<{ ok: boolean; detail?: string }> {
  try {
    const replace = options?.replace ?? false;
    const url = `${getBaseUrl()}/phrases${replace ? "?replace=true" : ""}`;
    const res = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      return { ok: false, detail: data.detail ?? `HTTP ${res.status}` };
    }
    return { ok: true };
  } catch (err) {
    return { ok: false, detail: String(err) };
  }
}

export async function importPhrases(
  payload: Partial<PhraseCatalog>,
  options?: { replace?: boolean },
): Promise<{ ok: boolean; detail?: string }> {
  try {
    const replace = options?.replace ?? false;
    const url = `${getBaseUrl()}/phrases/import${replace ? "?replace=true" : ""}`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      return { ok: false, detail: data.detail ?? `HTTP ${res.status}` };
    }
    return { ok: true };
  } catch (err) {
    return { ok: false, detail: String(err) };
  }
}

export async function resetPhrases(): Promise<boolean> {
  try {
    const res = await fetch(`${getBaseUrl()}/phrases/reset`, { method: "POST" });
    return res.ok;
  } catch {
    return false;
  }
}

