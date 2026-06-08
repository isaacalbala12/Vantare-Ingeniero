import { checkForUpdate, UpdateCheckResult } from "./api";

export type UpdateNotice = UpdateCheckResult & {
  dismissed: boolean;
};

let cachedNotice: UpdateNotice | null = null;

export async function fetchUpdateNotice(force = false): Promise<UpdateNotice | null> {
  if (!force && cachedNotice) {
    return cachedNotice;
  }
  const result = await checkForUpdate();
  if (!result) {
    return null;
  }
  cachedNotice = { ...result, dismissed: false };
  return cachedNotice;
}

import { getPlatform } from "../core/platform";

export async function openReleaseUrl(url: string): Promise<void> {
  if (!url) return;
  await getPlatform().openExternal(url);
}
