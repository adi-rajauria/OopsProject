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
      <Card flush title={
        <label className="flex items-center gap-2 text-[13px] text-muted">
          <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} /> Unread only
        </label>
      }>
        {inbox.error && <div className="p-4"><ErrorMessage error={inbox.error} onRetry={inbox.reload} /></div>}
        {inbox.loading && !inbox.data && <div className="px-4"><Spinner /></div>}
        {inbox.data?.length === 0 && <EmptyState title="You're all caught up" />}
        <ul className="divide-y divide-line">
          {inbox.data?.map((n) => (
            <li key={n.id} className={`flex items-start gap-3 px-4 py-3 ${n.is_read ? "" : "shadow-[inset_3px_0_0_var(--c-brand)]"}`}>
              <span aria-label={n.is_read ? undefined : "unread"} className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${n.is_read ? "bg-transparent" : "bg-brand"}`} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className={n.is_read ? "text-fg" : "font-semibold text-fg"}>{n.title}</span>
                  <time className="text-[12px] text-faint tabular-nums" title={formatDateTime(n.created_at)}>{relativeTime(n.created_at)}</time>
                </div>
                <p className="text-sm text-muted">{n.body}</p>
                <div className="mt-1 flex gap-3 text-xs">
                  <span className="font-mono text-[11.5px] text-faint">{titleCase(n.type)}</span>
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
