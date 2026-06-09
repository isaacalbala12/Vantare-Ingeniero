import path from "node:path";

const SAFE_FILENAME = /^[\w-]+\.json$/i;

export function resolveHistoryFile(historyDir: string, filename: string): string {
  if (!SAFE_FILENAME.test(filename)) {
    throw new Error("Invalid history filename");
  }
  const resolved = path.resolve(historyDir, filename);
  const dirResolved = path.resolve(historyDir);
  if (!resolved.startsWith(`${dirResolved}${path.sep}`) && resolved !== dirResolved) {
    throw new Error("Path traversal blocked");
  }
  return resolved;
}
