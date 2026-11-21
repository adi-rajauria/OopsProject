import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { notificationsApi } from "../api/endpoints";
import type { Notification } from "../api/types";
import { useLiveRefresh } from "../hooks/LiveEvents";
import { relativeTime } from "../lib/format";
import { BellIcon } from "./icons";

const REFRESH_MS = 60_000;

export function NotificationBell() {
  const [count, setCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const navigate = useNavigate();
  const panel = useRef<HTMLDivElement>(null);

  const refreshCount = () => notificationsApi.unreadCount().then((r) => setCount(r.count)).catch(() => {});
  useEffect(() => {
    refreshCount();
    const timer = setInterval(refreshCount, REFRESH_MS);
    return () => clearInterval(timer);
  }, []);
  // Live: any incident event may have produced a notification for me.
  useLiveRefresh(() => setTimeout(refreshCount, 300));

  useEffect(() => {
    if (!open) return;
    notificationsApi.inbox(false, 8).then(setItems).catch(() => {});
    const close = (e: MouseEvent) => {
      if (panel.current && !panel.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const openNotification = async (n: Notification) => {
    if (!n.is_read) {
      await notificationsApi.markRead(n.id).catch(() => {});
      refreshCount();
    }
    setOpen(false);
    if (n.incident_id) navigate(`/incidents/${n.incident_id}`);
  };

  return (
    <div className="relative" ref={panel}>
      <button
        className="relative grid h-8 w-8 place-items-center rounded text-muted hover:bg-sunken hover:text-fg"
        aria-label={`Notifications: ${count} unread`}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <BellIcon size={17} />
        {count > 0 && (
          <span className="absolute top-0.5 right-0 min-w-4 rounded-[3px] bg-critical-solid px-1 text-center font-mono text-[10px] leading-4 font-medium text-white">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-1.5 w-96 max-w-[calc(100vw-2rem)] overflow-hidden rounded-md border border-line bg-surface shadow-pop">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <span className="text-[13px] font-semibold">Notifications</span>
            <button
              className="text-[12px] font-medium text-brand hover:underline"
              onClick={async () => {
                await notificationsApi.markAllRead();
                setItems((all) => all.map((n) => ({ ...n, is_read: true })));
                setCount(0);
              }}
            >
              Mark all read
            </button>
          </div>
          <ul className="max-h-96 divide-y divide-line overflow-y-auto">
            {items.length === 0 && <li className="px-4 py-8 text-center text-[13px] text-muted">Nothing yet</li>}
            {items.map((n) => (
              <li key={n.id}>
                <button
                  className="relative block w-full px-4 py-2.5 text-left hover:bg-sunken"
                  onClick={() => openNotification(n)}
                >
                  {!n.is_read && <span aria-label="unread" className="absolute top-4 left-1.5 h-1.5 w-1.5 rounded-full bg-brand" />}
                  <div className="flex items-start justify-between gap-3">
                    <span className={`text-[13px] ${n.is_read ? "text-muted" : "font-medium text-fg"}`}>{n.title}</span>
                    <span className="shrink-0 font-mono text-[11px] text-faint">{relativeTime(n.created_at)}</span>
                  </div>
                  <p className="line-clamp-2 text-[12px] text-muted">{n.body}</p>
                </button>
              </li>
            ))}
          </ul>
          <Link to="/notifications" onClick={() => setOpen(false)}
                className="block border-t border-line px-4 py-2 text-center text-[13px] font-medium text-brand hover:bg-sunken">
            View all notifications
          </Link>
        </div>
      )}
    </div>
  );
}
