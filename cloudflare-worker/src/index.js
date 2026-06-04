/**
 * Vantare LLM Proxy — Cloudflare Worker
 *
 * Proxies OpenAI-compatible requests to Stepfun API with:
 *  - License key validation (X-License-Key header)
 *  - Rate limiting via KV (per-key and per-IP)
 *  - Structured usage logging (JSON to stdout)
 */

const VALID_PATHS = ["/v1/chat/completions"];
const STEPFUN_URL = "https://api.stepfun.com/v1/chat/completions";

function getValidKeys(env) {
  if (!env.LICENSE_KEYS) return [];
  if (typeof env.LICENSE_KEYS === "string") {
    return env.LICENSE_KEYS.split(",").map((k) => k.trim()).filter(Boolean);
  }
  if (Array.isArray(env.LICENSE_KEYS)) return env.LICENSE_KEYS;
  return [];
}

function isValidKey(key, env) {
  return getValidKeys(env).includes(key);
}

function maskKey(key) {
  if (!key || key.length < 8) return "***";
  return key.slice(0, 8) + "****";
}

async function checkRateLimit(request, env, keyPrefix) {
  if (!env.RATE_LIMIT) return null;
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const perKeyMax = parseInt(env.RATE_LIMIT_PER_KEY || "60", 10);
  const perIpMax = parseInt(env.RATE_LIMIT_PER_IP || "600", 10);
  const windowSec = 60;
  const now = Math.floor(Date.now() / 1000);
  const windowStart = now - windowSec;

  async function countInWindow(namespace, prefix) {
    const list = await namespace.list({ prefix: prefix });
    return list.keys.filter((k) => {
      const ts = parseInt(k.name.split(":").pop(), 10);
      return ts >= windowStart;
    }).length;
  }

  if (keyPrefix) {
    const keyCount = await countInWindow(env.RATE_LIMIT, "key:" + keyPrefix);
    if (keyCount >= perKeyMax) {
      return { blocked: true, reason: "rate_limit_key", limit: perKeyMax };
    }
  }

  const ipCount = await countInWindow(env.RATE_LIMIT, "ip:" + ip);
  if (ipCount >= perIpMax) {
    return { blocked: true, reason: "rate_limit_ip", limit: perIpMax };
  }

  const keySuffix = keyPrefix ? "key:" + keyPrefix + ":" + now : "";
  const ipSuffix = "ip:" + ip + ":" + now;
  if (keySuffix) {
    await env.RATE_LIMIT.put(keySuffix, "1", { expirationTtl: windowSec + 10 });
  }
  await env.RATE_LIMIT.put(ipSuffix, "1", { expirationTtl: windowSec + 10 });
  return null;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== "POST" || !VALID_PATHS.includes(url.pathname)) {
      return new Response(JSON.stringify({ error: "not_found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    const licenseKey = request.headers.get("X-License-Key") || "";
    if (!licenseKey || !isValidKey(licenseKey, env)) {
      console.log(JSON.stringify({
        event: "license_rejected",
        key_prefix: licenseKey ? maskKey(licenseKey) : "none",
        timestamp: new Date().toISOString(),
        status: 401,
      }));
      return new Response(JSON.stringify({ error: "invalid_license_key" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }

    const keyPrefix = maskKey(licenseKey);
    const rateLimit = await checkRateLimit(request, env, keyPrefix);
    if (rateLimit) {
      return new Response(JSON.stringify({ error: "rate_limited", reason: rateLimit.reason }), {
        status: 429,
        headers: { "Content-Type": "application/json", "Retry-After": "60" },
      });
    }

    const stepfunKey = env.STEPFUN_API_KEY;
    if (!stepfunKey) {
      return new Response(JSON.stringify({ error: "proxy_config_error" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response(JSON.stringify({ error: "invalid_json" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    const stepfunResponse = await fetch(STEPFUN_URL, {
      method: "POST",
      headers: {
        Authorization: "Bearer " + stepfunKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    const ct = stepfunResponse.headers.get("content-type") || "application/json";
    console.log(JSON.stringify({
      event: "proxy_success",
      key_prefix: keyPrefix,
      model: body.model || "unknown",
      streaming: body.stream === true,
      status: stepfunResponse.status,
      timestamp: new Date().toISOString(),
    }));

    return new Response(stepfunResponse.body, {
      status: stepfunResponse.status,
      headers: { "Content-Type": ct, "Cache-Control": "no-store" },
    });
  },
};
