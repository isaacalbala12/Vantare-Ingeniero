import { shell } from "electron";

const ALLOWED_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

export function openExternalUrl(url: string): Promise<void> {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return Promise.reject(new Error("Invalid URL"));
  }
  if (!ALLOWED_PROTOCOLS.has(parsed.protocol)) {
    return Promise.reject(new Error(`Blocked protocol: ${parsed.protocol}`));
  }
  return shell.openExternal(parsed.toString());
}
