import type { PlatformBridge, SessionHistoryFile } from "./types";

const emptyHistory: SessionHistoryFile = {
  sessionId: "",
  startedAt: "",
  messages: [],
};

const webStub: PlatformBridge = {
  isElectron: false,
  isTauri: false,
  openExternal: async (url) => {
    window.open(url, "_blank", "noopener,noreferrer");
  },
  duckLmu: async () => {},
  saveSessionHistory: async () => "web-noop",
  listSessionHistories: async () => [],
  loadSessionHistory: async () => emptyHistory,
  setOverlayResizeMode: async () => {},
  toggleOverlay: async () => {},
  showOverlay: async () => {},
  hideOverlay: async () => {},
  setOverlayPresentation: async () => {},
  subscribePtt: undefined,
  updatePttHotkeys: undefined,
};

export function getPlatform(): PlatformBridge {
  const bridge = (window as Window & { vantare?: Partial<PlatformBridge> }).vantare;
  if (bridge?.isElectron) {
    return {
      isElectron: true,
      isTauri: false,
      openExternal: bridge.openExternal ?? webStub.openExternal,
      duckLmu: bridge.duckLmu ?? webStub.duckLmu,
      saveSessionHistory: bridge.saveSessionHistory ?? webStub.saveSessionHistory,
      listSessionHistories: bridge.listSessionHistories ?? webStub.listSessionHistories,
      loadSessionHistory: bridge.loadSessionHistory ?? webStub.loadSessionHistory,
      setOverlayResizeMode: bridge.setOverlayResizeMode ?? webStub.setOverlayResizeMode,
      toggleOverlay: bridge.toggleOverlay ?? webStub.toggleOverlay,
      showOverlay: bridge.showOverlay ?? webStub.showOverlay,
      hideOverlay: bridge.hideOverlay ?? webStub.hideOverlay,
      setOverlayPresentation: bridge.setOverlayPresentation ?? webStub.setOverlayPresentation,
      reportOverlaySize: bridge.reportOverlaySize,
      subscribePtt: bridge.subscribePtt,
      updatePttHotkeys: bridge.updatePttHotkeys,
      getDesktopUpdateStatus: bridge.getDesktopUpdateStatus,
      checkDesktopUpdates: bridge.checkDesktopUpdates,
      downloadDesktopUpdate: bridge.downloadDesktopUpdate,
      quitAndInstallDesktopUpdate: bridge.quitAndInstallDesktopUpdate,
      subscribeDesktopUpdate: bridge.subscribeDesktopUpdate,
    };
  }
  return webStub;
}

export type { PlatformBridge, SessionHistoryFile } from "./types";
