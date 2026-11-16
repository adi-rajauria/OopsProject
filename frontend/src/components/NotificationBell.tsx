import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { notificationsApi } from "../api/endpoints";
import type { Notification } from "../api/types";
import { useLiveRefresh } from "../hooks/LiveEvents";
import { relativeTime } from "../lib/format";

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
        className="relative rounded-full p-2 text-slate-600 hover:bg-slate-100"
        aria-label={`Notifications: ${count} unread`}
        onClick={() => setOpen((o) => !o)}
      >
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 1 0-12 0v3.2c0 .5-.2 1-.6 1.4L4 17h5m6 0a3 3 0 1 1-6 0m6 0H9" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {count > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-5 rounded-full bg-rose-600 px-1 text-center text-[11px] leading-5 font-semibold text-white">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-96 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
            <span className="text-sm font-semibold">Notifications</span>
            <button
              className="text-xs text-[var(--accent)] hover:underline"
              onClick={async () => {
                await notificationsApi.markAllRead();
                setItems((all) => all.map((n) => ({ ...n, is_read: true })));
                setCount(0);
              }}
            >
              Mark all read
            </button>
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {items.length === 0 && <li className="px-4 py-6 text-center text-sm text-slate-500">Nothing yet</li>}
            {items.map((n) => (
              <li key={n.id}>
                <button
                  className={`block w-full border-b border-slate-50 px-4 py-2.5 text-left hover:bg-slate-50 ${n.is_read ? "" : "bg-[var(--accent-soft)]/50"}`}
                  onClick={() => openNotification(n)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className={`text-sm ${n.is_read ? "text-slate-700" : "font-semibold text-slate-900"}`}>{n.title}</span>
                    <span className="shrink-0 text-xs text-slate-400">{relativeTime(n.created_at)}</span>
                  </div>
                  <p className="line-clamp-2 text-xs text-slate-500">{n.body}</p>
                </button>
              </li>
            ))}
          </ul>
          <Link to="/notifications" onClick={() => setOpen(false)} className="block px-4 py-2 text-center text-sm text-[var(--accent)] hover:bg-slate-50">
            View all
          </Link>
        </div>
      )}
    </div>
  );
}
