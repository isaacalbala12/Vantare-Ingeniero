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
  const vllmIP = config.vllmIP || "localhost";
  const serverPort = config.serverPort || 8008;
  return `http://${vllmIP}:${serverPort}`;
};

/**
 * Consulta el estado de salud del backend asíncrono
 */
export async function getHealth(): Promise<HealthResponse> {
  const url = `${getBaseUrl()}/health`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    const data = await res.json();
    return {
      status: data.status || "ok",
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
    console.error("[api] Error fetching health:", err);
    return {
      status: "error",
      shared_memory: { status: "offline", offline_mode: true, last_lap: 0 },
      lmu_api: { status: "idle", cache: {} },
      llm: { configured: false, model: "" },
      websocket: false,
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Recupera el registro histórico de consumo de combustible
 */
export interface LicenseValidationResponse {
  valid: boolean;
  message?: string;
}

export async function validateLicense(licenseKey: string): Promise<LicenseValidationResponse> {
  try {
    const url = `${getBaseUrl()}/api/config`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ license_key: licenseKey }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (res.ok) {
      const data = await res.json();
      return { valid: true, message: data.message ?? "Licencia activada correctamente" };
    }
    if (res.status === 404) {
      return { valid: true, message: "Licencia validada (modo desarrollo)" };
    }
    const data = await res.json().catch(() => ({}));
    return { valid: false, message: data.message ?? "Error al validar licencia" };
  } catch (err) {
    console.warn("[api] Error validating license:", err);
    return { valid: false, message: "No se pudo conectar con el servidor" };
  }
}

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

