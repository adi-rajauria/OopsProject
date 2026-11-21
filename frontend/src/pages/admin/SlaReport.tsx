import { Link } from "react-router";
import { intelligenceApi, reportsApi } from "../../api/endpoints";
import { PriorityBadge, RiskBadge, StatusBadge } from "../../components/badges";
import { Card, ErrorMessage, PageHeader, Spinner, Stat, StatStrip } from "../../components/ui";
import { useLiveRefresh } from "../../hooks/LiveEvents";
import { useAsync } from "../../hooks/useAsync";
import { formatDateTime, formatMinutes } from "../../lib/format";

/** SLA violations dashboard (spec dashboard #4) + compliance per priority + current risk. */
export function SlaReportPage() {
  const report = useAsync(() => reportsApi.sla(), []);
  const risks = useAsync(() => intelligenceApi.slaRisk("HIGH"), []);
  useLiveRefresh(() => {
    report.reload();
    risks.reload();
  });
  if (report.error) return <ErrorMessage error={report.error} onRetry={report.reload} />;
  if (!report.data) return <Spinner />;
  const { violations, compliance } = report.data;

  return (
    <>
      <PageHeader title="SLA monitoring" subtitle="Violations are detected by the background monitor (every 60 s) and when targets are met late." />
      <StatStrip columns={4}>
        {compliance.map((c) => (
          <Stat key={c.priority} label={`${c.priority} resolution compliance`}
                    value={c.compliance_pct !== null ? `${c.compliance_pct}%` : "—"}
                    tone={c.compliance_pct === null ? "default" : c.compliance_pct >= 90 ? "success" : c.compliance_pct >= 60 ? "warning" : "danger"}
                    hint={`${c.met} of ${c.evaluated} settled incidents met the target`} />
        ))}
      </StatStrip>

      <Card title="At high risk or already breached (open)" className="mt-6">
        {risks.data?.length === 0 && <p className="text-sm text-muted">No open incident is at high risk.</p>}
        <ul className="grid gap-3 md:grid-cols-2">
          {risks.data?.map((r) => (
            <li key={r.incident_id} className="rounded border border-line px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span>
                  <Link className="link mono" to={`/incidents/${r.incident_id}`}>{r.number}</Link>{" "}
                  <PriorityBadge priority={r.priority} />
                </span>
                <RiskBadge level={r.level} />
              </div>
              <p className="text-fg">{r.title}</p>
              <p className="text-xs text-muted">{r.reasons.join(" · ")}</p>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={`Recorded violations (${violations.length})`} className="mt-6">
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr><th>Incident</th><th>Priority</th><th>Status</th><th>Service</th><th>Technician</th><th>Target</th><th>Due</th><th>Overdue</th></tr>
            </thead>
            <tbody>
              {violations.map((v) => (
                <tr key={`${v.incident_id}-${v.target}`}>
                  <td>
                    <Link className="link mono" to={`/incidents/${v.incident_id}`}>{v.number}</Link>
                    <div className="max-w-xs truncate text-fg">{v.title}</div>
                  </td>
                  <td><PriorityBadge priority={v.priority} /></td>
                  <td><StatusBadge status={v.status} /></td>
                  <td className="text-muted">{v.service}</td>
                  <td className="text-muted">{v.technician ?? "—"}</td>
                  <td className="text-xs font-medium">{v.target === "RESPONSE" ? "Response" : "Resolution"}</td>
                  <td className="text-xs whitespace-nowrap text-muted">{formatDateTime(v.due_at)}</td>
                  <td className="font-medium whitespace-nowrap text-critical tabular-nums">{formatMinutes(v.overdue_minutes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
