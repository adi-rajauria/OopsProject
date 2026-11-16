import { useState } from "react";
import { Link } from "react-router";
import { notificationsApi } from "../../api/endpoints";
import { useToast } from "../../components/Toasts";
import { Card, EmptyState, ErrorMessage, PageHeader, Spinner } from "../../components/ui";
import { useLiveRefresh } from "../../hooks/LiveEvents";
import { useAsync } from "../../hooks/useAsync";
import { formatDateTime, relativeTime, titleCase } from "../../lib/format";

export function NotificationsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const inbox = useAsync(() => notificationsApi.inbox(unreadOnly, 100), [unreadOnly]);
  const toast = useToast();
  useLiveRefresh(() => setTimeout(inbox.reload, 300));

  const markAll = async () => {
    const result = await notificationsApi.markAllRead();
    toast.success(`${result.count} notification(s) marked as read`);
    inbox.reload();
  };

  return (
    <>
      <PageHeader title="Notifications" subtitle="In-app messages. E-mail and SMS copies are sent (simulated) for important events."
                  actions={<button className="btn-secondary" onClick={markAll}>Mark all as read</button>} />
      <Card title={
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} /> Unread only
        </label>
      }>
        {inbox.error && <ErrorMessage error={inbox.error} onRetry={inbox.reload} />}
        {inbox.loading && !inbox.data && <Spinner />}
        {inbox.data?.length === 0 && <EmptyState title="You're all caught up" />}
        <ul className="divide-y divide-slate-100">
          {inbox.data?.map((n) => (
            <li key={n.id} className={`flex items-start gap-3 py-3 ${n.is_read ? "" : "-mx-2 rounded-lg bg-[var(--accent-soft)]/40 px-2"}`}>
              <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.is_read ? "bg-transparent" : "bg-[var(--accent)]"}`} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className={n.is_read ? "text-slate-700" : "font-semibold text-slate-900"}>{n.title}</span>
                  <time className="text-xs text-slate-400" title={formatDateTime(n.created_at)}>{relativeTime(n.created_at)}</time>
                </div>
                <p className="text-sm text-slate-600">{n.body}</p>
                <div className="mt-1 flex gap-3 text-xs">
                  <span className="text-slate-400">{titleCase(n.type)}</span>
                  {n.incident_id && <Link className="link" to={`/incidents/${n.incident_id}`}>Open {n.incident_number}</Link>}
                  {!n.is_read && (
                    <button className="link" onClick={async () => { await notificationsApi.markRead(n.id); inbox.reload(); }}>
                      Mark read
                    </button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
