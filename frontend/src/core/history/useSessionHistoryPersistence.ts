import { useEffect, useRef } from "react";
import { useAppStore } from "../../store/config";
import { getPlatform } from "../platform";
import type { SessionHistoryFile } from "../platform/types";

function sessionFilename(session: SessionHistoryFile): string {
  const stamp = session.startedAt.slice(0, 10).replace(/-/g, "");
  return `${stamp}-${session.sessionId}.json`;
}

export function sessionHistoryFilename(session: SessionHistoryFile): string {
  return sessionFilename(session);
}

export function useSessionHistoryPersistence(): void {
  const messages = useAppStore((s) => s.radio.messageHistory);
  const sessionRef = useRef<SessionHistoryFile>({
    sessionId: crypto.randomUUID(),
    startedAt: new Date().toISOString(),
    messages: [],
  });
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    sessionRef.current.messages = messages;
    if (messages.length === 0) return;

    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      void getPlatform().saveSessionHistory(sessionRef.current);
    }, 2000);
  }, [messages]);

  useEffect(() => {
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      if (sessionRef.current.messages.length > 0) {
        sessionRef.current.endedAt = new Date().toISOString();
        void getPlatform().saveSessionHistory(sessionRef.current);
      }
    };
  }, []);
}
