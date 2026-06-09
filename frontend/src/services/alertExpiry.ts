/** Derive absolute expiry from WS alert / commentary payload (Crew Chief ttl contract). */
export function expiresAtFromPayload(payload?: Record<string, unknown>): number | undefined {
  if (!payload) return undefined;

  const inner = (payload.payload ?? {}) as Record<string, unknown>;
  const ttlMs = inner.ttl_ms ?? payload.ttl_ms;
  if (typeof ttlMs === "number" && ttlMs > 0) {
    return Date.now() + ttlMs;
  }

  const ttlSec = payload.ttl;
  if (typeof ttlSec === "number" && ttlSec > 0) {
    return Date.now() + ttlSec * 1000;
  }

  return undefined;
}

/** Absolute play time when backend/FE defers TTS during hard-parts. */
export function delayedUntilFromPayload(payload?: Record<string, unknown>): number | undefined {
  if (!payload) return undefined;
  const inner = (payload.payload ?? {}) as Record<string, unknown>;
  const raw = inner.delayed_until_ms ?? payload.delayed_until_ms;
  if (typeof raw === "number" && raw > 0) {
    return raw;
  }
  return undefined;
}

export function validationKeyFromPayload(payload?: Record<string, unknown>): string | undefined {
  if (!payload) return undefined;
  const inner = (payload.payload ?? {}) as Record<string, unknown>;
  const raw = inner.validation_key ?? payload.validation_key;
  return typeof raw === "string" && raw.length > 0 ? raw : undefined;
}

export function isExpiredAt(expiresAt?: number, now = Date.now()): boolean {
  return typeof expiresAt === "number" && expiresAt <= now;
}
