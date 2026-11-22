import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { adminApi } from "../../api/endpoints";
import { Card, ErrorMessage, PageHeader, Spinner, Tabs } from "../../components/ui";
import { useAsync } from "../../hooks/useAsync";
import { formatDateTime, titleCase } from "../../lib/format";

const PAGE = 50;
const ACTIONS = ["CREATED", "CLASSIFIED", "PRIORITY_CALCULATED", "PRIORITY_CHANGED", "ASSIGNED", "ACKNOWLEDGE", "START_WORK",
  "REQUEST_INFO", "PROVIDE_INFO", "RESOLVE", "REOPEN", "VERIFY", "CLOSE", "COMMENT_ADDED", "UPDATED", "SLA_WARNING",
  "SLA_VIOLATED", "ESCALATED", "RELATED_DETECTED", "FEEDBACK", "USER_CREATED", "USER_UPDATED", "USER_DEACTIVATED",
  "TECHNICIAN_UPDATED", "SETTING_CHANGED", "SERVICE_CREATED", "SERVICE_UPDATED", "SERVICE_DEPENDENCIES_CHANGED",
  "CATEGORY_CREATED", "CATEGORY_UPDATED", "SLA_POLICY_CREATED", "SLA_POLICY_UPDATED", "SLA_POLICY_DELETED"];

function AuditTable() {
  const [params, setParams] = useSearchParams();
  const offset = Number(params.get("offset") ?? 0);
  const action = params.get("action") ?? "";
  const incident = params.get("incident") ?? "";
  const [draft, setDraft] = useState(incident);
  const incidentId = /^\D*(\d+)$/.exec(incident)?.[1];
  const records = useAsync(() => adminApi.auditLogs({
    limit: PAGE, offset, action: action || null,
    // "DCN-1005" / "1005" are incident numbers; small numbers are treated as raw ids
    incident_id: incidentId ? (Number(incidentId) > 1000 ? Number(incidentId) - 1000 : Number(incidentId)) : null,
  }), [offset, action, incident]);

  const apply = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    if (!("offset" in changes)) next.delete("offset");
    setParams(next);
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    apply({ incident: draft.trim() });
  };

  return (
    <Card title={
      <form className="flex flex-wrap gap-2" onSubmit={submit}>
        <select className="input w-auto" aria-label="Action" value={action} onChange={(e) => apply({ action: e.target.value })}>
          <option value="">All actions</option>
          {ACTIONS.map((a) => <option key={a} value={a}>{titleCase(a)}</option>)}
        </select>
        <input className="input w-36" placeholder="DCN-1001" aria-label="Incident" value={draft} onChange={(e) => setDraft(e.target.value)} />
        <button className="btn-secondary btn-sm">Filter</button>
      </form>
    }>
      {records.error && <ErrorMessage error={records.error} onRetry={records.reload} />}
      {!records.data ? <Spinner /> : (
        <>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Incident</th><th>State change</th><th>Description</th></tr></thead>
              <tbody>
                {records.data.map((r) => (
                  <tr key={r.id}>
                    <td className="text-xs whitespace-nowrap text-muted">{formatDateTime(r.created_at)}</td>
                    <td className="text-xs whitespace-nowrap">{r.actor_name}</td>
                    <td className="text-xs font-semibold whitespace-nowrap">{titleCase(r.action)}</td>
                    <td>{r.incident_id ? <Link className="link mono" to={`/incidents/${r.incident_id}`}>{r.incident_number}</Link> : "—"}</td>
                    <td className="font-mono text-[11px] whitespace-nowrap text-muted">
                      {r.new_state ? `${r.previous_state ?? "∅"} → ${r.new_state}` : ""}
                    </td>
                    <td className="text-sm text-fg">{r.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end gap-2 pt-3">
            <button className="btn-secondary btn-sm" disabled={offset === 0} onClick={() => apply({ offset: String(Math.max(0, offset - PAGE)) })}>Newer</button>
            <button className="btn-secondary btn-sm" disabled={records.data.length < PAGE} onClick={() => apply({ offset: String(offset + PAGE) })}>Older</button>
          </div>
        </>
      )}
    </Card>
  );
}

function DeliveryLog() {
  const log = useAsync(() => adminApi.deliveryLog(300), []);
  if (log.error) return <ErrorMessage error={log.error} onRetry={log.reload} />;
  if (!log.data) return <Spinner />;
  return (
    <Card title="Notification delivery log (in-app, simulated e-mail and SMS)">
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead><tr><th>Time</th><th>Channel</th><th>Recipient</th><th>Message</th><th>Incident</th><th>Delivery</th></tr></thead>
          <tbody>
            {log.data.map((n) => (
              <tr key={n.id}>
                <td className="text-xs whitespace-nowrap text-muted">{formatDateTime(n.created_at)}</td>
                <td><span className="rounded bg-sunken px-1.5 py-0.5 text-xs font-semibold">{n.channel.replace("_", "-")}</span></td>
                <td className="text-xs">user #{n.recipient_id}</td>
                <td><div className="text-sm font-medium">{n.title}</div><div className="text-xs text-muted">{n.body}</div></td>
                <td>{n.incident_id ? <Link className="link mono" to={`/incidents/${n.incident_id}`}>{n.incident_number}</Link> : "—"}</td>
                <td className="text-xs">{n.delivered ? <span className="text-ok">delivered</span> : <span className="text-critical" title={n.delivery_error ?? ""}>failed: {n.delivery_error}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function AuditLogPage() {
  const [tab, setTab] = useState<"audit" | "delivery">("audit");
  return (
    <>
      <PageHeader title="Audit log" subtitle="Append-only history: who did what, when, and the state before and after." />
      <Tabs tabs={[{ key: "audit", label: "Audit records" }, { key: "delivery", label: "Notification deliveries" }]} active={tab} onChange={setTab} />
      {tab === "audit" ? <AuditTable /> : <DeliveryLog />}
    </>
  );
}
