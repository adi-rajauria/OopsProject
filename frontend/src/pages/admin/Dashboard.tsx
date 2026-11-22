import { Link } from "react-router";
import { adminApi, incidentsApi, intelligenceApi, reportsApi } from "../../api/endpoints";
import { ALL_PRIORITIES } from "../../api/types";
import { PriorityBadge, RiskBadge } from "../../components/badges";
import { BarList, Stars, TrendChart } from "../../components/charts";
import { IncidentTable } from "../../components/IncidentTable";
import { useToast } from "../../components/Toasts";
import { Card, ErrorMessage, PageHeader, Spinner, Stat, StatStrip } from "../../components/ui";
import { useLiveEvents, useLiveRefresh } from "../../hooks/LiveEvents";
import { useAsync } from "../../hooks/useAsync";
import { formatMinutes, formatTime, PRIORITY_LABEL, STATUS_LABEL, titleCase } from "../../lib/format";

function LiveFeed() {
  const { recent, connected } = useLiveEvents();
  return (
    <Card title="Live activity" flush
          actions={<span className="flex items-center gap-1.5 text-[12px] text-muted">
            <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-ok-solid" : "bg-faint"}`} />
            {connected ? "streaming" : "reconnecting"}
          </span>}>
      {recent.length === 0 && <p className="p-4 text-[13px] text-muted">Events appear here the moment they happen (server-sent events).</p>}
      <ul className="max-h-[30rem] divide-y divide-line overflow-y-auto">
        {recent.map((e, index) => (
          <li key={`${e.at}-${index}`} className="px-4 py-2 text-[13px]">
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[11.5px] text-faint tabular-nums">{formatTime(e.at)}</span>
              <Link className="link mono" to={`/incidents/${e.incident_id}`}>{e.number}</Link>
              <span className="text-[12px] font-medium text-fg">{titleCase(e.action)}</span>
            </div>
            <p className="text-muted">{e.description}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

const PRIORITY_BAR: Record<string, string> = {
  P1: "bg-critical-solid",
  P2: "bg-critical-solid/50",
  P3: "bg-warning-solid",
  P4: "bg-line-strong",
};

export function AdminDashboardPage() {
  const toast = useToast();
  const overview = useAsync(() => reportsApi.overview(), []);
  const trends = useAsync(() => reportsApi.trends(14), []);
  const risks = useAsync(() => intelligenceApi.slaRisk("MEDIUM"), []);
  const unassigned = useAsync(() => incidentsApi.search({ unassigned: true, open_only: true, sort: "priority", page_size: 5 }), []);
  useLiveRefresh(() => {
    overview.reload();
    risks.reload();
    unassigned.reload();
  });

  const runCheck = async () => {
    try {
      const r = await adminApi.checkSlaNow();
      toast.success(`SLA check: ${r.checked} open incidents, ${r.warnings} warnings, ${r.violations} new violations, ${r.escalations} escalations`);
      overview.reload();
      risks.reload();
    } catch (err) {
      toast.error(err);
    }
  };

  if (overview.error) return <ErrorMessage error={overview.error} onRetry={overview.reload} />;
  if (!overview.data) return <Spinner />;
  const o = overview.data;

  return (
    <>
      <PageHeader title="Operations dashboard" subtitle="Live view of incidents, SLA compliance and risk across all services."
                  actions={<button className="btn-secondary" onClick={runCheck}>Run SLA check now</button>} />

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-6">
          <Card title={<h2 className="flex items-center gap-2 text-[13.5px]"><span className="h-2 w-2 bg-critical-solid" />Likely to breach</h2>} flush
                actions={<Link className="link" to="/admin/sla">SLA report</Link>}>
            {!risks.data && !risks.error && <div className="px-4"><Spinner /></div>}
            {risks.data?.length === 0 && <p className="p-4 text-[13px] text-muted">Nothing at risk right now.</p>}
            {risks.data && risks.data.length > 0 && (
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead><tr><th>Incident</th><th>Priority</th><th>Risk</th><th>Target</th><th>Why</th></tr></thead>
                  <tbody>
                    {risks.data.slice(0, 8).map((r) => (
                      <tr key={r.incident_id}>
                        <td className="min-w-48">
                          <Link className="link mono" to={`/incidents/${r.incident_id}`}>{r.number}</Link>
                          <div className="text-fg">{r.title}</div>
                        </td>
                        <td><PriorityBadge priority={r.priority} /></td>
                        <td>
                          <RiskBadge level={r.level} />
                          <div className="mt-0.5 font-mono text-[11px] text-faint">score {r.risk_score}</div>
                        </td>
                        <td className="text-[12.5px] whitespace-nowrap tabular-nums">
                          <span className="text-muted">{r.target.toLowerCase()}</span><br />
                          {r.minutes_left >= 0
                            ? `${formatMinutes(r.minutes_left)} left`
                            : <span className="font-medium text-critical">{formatMinutes(-r.minutes_left)} over</span>}
                        </td>
                        <td className="min-w-56 text-[12px] text-muted">{r.reasons.join(" · ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title={<h2 className="flex items-center gap-2 text-[13.5px]"><span className="h-2 w-2 bg-warning-solid" />Waiting for a technician</h2>} flush
                actions={<Link className="link" to="/incidents?unassigned=true&open_only=true">View all</Link>}>
            {unassigned.data ? (
              <IncidentTable incidents={unassigned.data.items} columns={["service", "reporter", "due"]} empty="Every open incident has a technician" />
            ) : <div className="px-4"><Spinner /></div>}
          </Card>
        </div>
        <LiveFeed />
      </div>

      <div className="mt-6">
        <StatStrip columns={6}>
          <Stat label="Total incidents" value={o.total} />
          <Stat label="Open" value={o.open} hint={`${o.unassigned} unassigned`} tone={o.unassigned ? "warning" : "default"} />
          <Stat label="Critical open" value={o.critical_open} tone={o.critical_open ? "danger" : "default"} hint="P1 incidents" />
          <Stat label="Resolved" value={o.resolved} hint={`${o.closed} closed`} />
          <Stat label="SLA violations" value={o.sla_violations} tone={o.sla_violations ? "danger" : "default"}
                hint={`${o.breached_open} open & breached · ${o.at_risk} at risk`} />
          <Stat label="Mean time to resolve" value={o.mttr_hours !== null ? `${o.mttr_hours} h` : "—"}
                hint={o.avg_rating !== null ? <span className="inline-flex items-center gap-1.5"><Stars rating={Math.round(o.avg_rating)} size={11} />{o.avg_rating}</span> : "no feedback yet"} />
        </StatStrip>
      </div>

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card title="Created vs resolved, last 14 days">
          {trends.data ? <TrendChart points={trends.data} /> : <Spinner />}
        </Card>
        <Card title="Open incidents by priority">
          <BarList items={ALL_PRIORITIES.map((p) => ({
            label: PRIORITY_LABEL[p], value: o.by_priority_open[p] ?? 0, colour: PRIORITY_BAR[p],
          }))} />
          <h3 className="mt-6 mb-3">All incidents by status</h3>
          <BarList colour="bg-line-strong"
                   items={Object.entries(o.by_status).map(([s, v]) => ({ label: STATUS_LABEL[s as keyof typeof STATUS_LABEL], value: v ?? 0 }))} />
        </Card>
      </div>
    </>
  );
}
