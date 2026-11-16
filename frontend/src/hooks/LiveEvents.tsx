import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { tokenStore } from "../api/client";
import type { LiveEvent } from "../api/types";

type Listener = (event: LiveEvent) => void;

interface LiveEventsValue {
  connected: boolean;
  recent: LiveEvent[];
  subscribe: (listener: Listener) => () => void;
}

const LiveEventsContext = createContext<LiveEventsValue | null>(null);
const RECENT_LIMIT = 30;

/** One Server-Sent-Events connection per signed-in session, shared by every page. */
export function LiveEventsProvider({ userId, children }: { userId: number; children: ReactNode }) {
  const listeners = useRef(new Set<Listener>());
  const [connected, setConnected] = useState(false);
  const [recent, setRecent] = useState<LiveEvent[]>([]);

  useEffect(() => {
    const token = tokenStore.get();
    if (!token) return;
    const source = new EventSource(`/api/stream/events?token=${encodeURIComponent(token)}`);
    source.addEventListener("ready", () => setConnected(true));
    source.addEventListener("incident", (message) => {
      const event = JSON.parse((message as MessageEvent<string>).data) as LiveEvent;
      setRecent((all) => [event, ...all].slice(0, RECENT_LIMIT));
      listeners.current.forEach((listener) => listener(event));
    });
    source.onerror = () => setConnected(false); // EventSource retries automatically
    return () => source.close();
  }, [userId]);

  const value: LiveEventsValue = {
    connected,
    recent,
    subscribe: (listener) => {
      listeners.current.add(listener);
      return () => {
        listeners.current.delete(listener);
      };
    },
  };
  return <LiveEventsContext.Provider value={value}>{children}</LiveEventsContext.Provider>;
}

export function useLiveEvents(): LiveEventsValue {
  const ctx = useContext(LiveEventsContext);
  if (!ctx) throw new Error("useLiveEvents must be used inside <LiveEventsProvider>");
  return ctx;
}

/** Calls `onEvent` for every live event (optionally only for one incident). */
export function useLiveRefresh(onEvent: (event: LiveEvent) => void, incidentId?: number) {
  const { subscribe } = useLiveEvents();
  const handler = useRef(onEvent);
  handler.current = onEvent;
  useEffect(
    () =>
      subscribe((event) => {
        if (incidentId === undefined || event.incident_id === incidentId) handler.current(event);
      }),
    [incidentId],
  );
}
