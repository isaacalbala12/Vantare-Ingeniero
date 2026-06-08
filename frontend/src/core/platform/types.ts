export type HistorySender = "pilot" | "engineer" | "spotter";

export interface SessionHistoryFile {
  sessionId: string;
  startedAt: string;
  endedAt?: string;
  track?: string;
  messages: Array<{ sender: HistorySender; text: string; timestamp: number; category?: string }>;
}

export interface PttHotkeyPayload {
  start: string;
  stop: string;
}

export type OverlayPresentation = "hidden" | "listening" | "speaking";

export type DesktopUpdatePhase =
  | "idle"
  | "checking"
  | "available"
  | "not-available"
  | "downloading"
  | "downloaded"
  | "error";

export interface DesktopUpdateStatus {
  phase: DesktopUpdatePhase;
  currentVersion: string;
  latestVersion?: string;
  percent?: number;
  bytesPerSecond?: number;
  transferred?: number;
  total?: number;
  message?: string;
}

export interface PlatformBridge {
  isElectron: boolean;
  isTauri: boolean;
  openExternal(url: string): Promise<void>;
  duckLmu(active: boolean, level?: number): Promise<void>;
  saveSessionHistory(payload: SessionHistoryFile): Promise<string>;
  listSessionHistories(): Promise<string[]>;
  loadSessionHistory(filename: string): Promise<SessionHistoryFile>;
  setOverlayResizeMode(enabled: boolean): Promise<void>;
  toggleOverlay(): Promise<void>;
  showOverlay(): Promise<void>;
  hideOverlay(): Promise<void>;
  setOverlayPresentation?(presentation: OverlayPresentation): Promise<void>;
  reportOverlaySize?(size: { width: number; height: number }): void;
  subscribePtt?(handler: (action: "down" | "up" | "toggle") => void): () => void;
  updatePttHotkeys?(payload: PttHotkeyPayload): Promise<void>;
  getDesktopUpdateStatus?(): Promise<DesktopUpdateStatus>;
  checkDesktopUpdates?(): Promise<DesktopUpdateStatus>;
  downloadDesktopUpdate?(): Promise<void>;
  quitAndInstallDesktopUpdate?(): Promise<void>;
  subscribeDesktopUpdate?(handler: (status: DesktopUpdateStatus) => void): () => void;
}

export type ElectronBridge = PlatformBridge & { isElectron: true };
