import { Link } from "react-router";
import { adminApi, incidentsApi, intelligenceApi, reportsApi } from "../../api/endpoints";
import { ALL_PRIORITIES } from "../../api/types";
import { PriorityBadge, RiskBadge } from "../../components/badges";
import { BarList, Stars, TrendChart } from "../../components/charts";
import { IncidentTable } from "../../components/IncidentTable";
import { useToast } from "../../components/Toasts";
import { Card, ErrorMessage, PageHeader, Spinner, StatCard } from "../../components/ui";
import { useLiveEvents, useLiveRefresh } from "../../hooks/LiveEvents";
import { useAsync } from "../../hooks/useAsync";
import { formatMinutes, formatTime, PRIORITY_LABEL, STATUS_LABEL, titleCase } from "../../lib/format";

function LiveFeed() {
  const { recent, connected } = useLiveEvents();
  return (
    <Card title="Live activity" actions={<span className={`text-xs ${connected ? "text-emerald-600" : "text-slate-400"}`}>{connected ? "● streaming" : "○ reconnecting"}</span>}>
      {recent.length === 0 && <p className="text-sm text-slate-500">Events appear here the moment they happen (SSE).</p>}
      <ul className="max-h-96 space-y-2 overflow-y-auto">
        {recent.map((e, index) => (
          <li key={`${e.at}-${index}`} className="text-sm">
            <span className="mr-2 text-xs text-slate-400 tabular-nums">{formatTime(e.at)}</span>
            <Link className="link font-mono text-xs" to={`/incidents/${e.incident_id}`}>{e.number}</Link>{" "}
            <span className="text-xs font-semibold text-slate-600">{titleCase(e.action)}</span>
            <p className="text-slate-600">{e.description}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

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
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
        <StatCard label="Total incidents" value={o.total} />
        <StatCard label="Open" value={o.open} hint={`${o.unassigned} unassigned`} tone={o.unassigned ? "warning" : "default"} />
        <StatCard label="Critical open" value={o.critical_open} tone={o.critical_open ? "danger" : "default"} hint="P1 incidents" />
        <StatCard label="Resolved" value={o.resolved} hint={`${o.closed} closed`} tone="success" />
        <StatCard label="SLA violations" value={o.sla_violations} tone="danger" hint={`${o.breached_open} open & breached, ${o.at_risk} at risk`} />
        <StatCard label="MTTR" value={o.mttr_hours !== null ? `${o.mttr_hours} h` : "—"}
                  hint={o.avg_rating !== null ? <>Satisfaction <Stars rating={Math.round(o.avg_rating)} /> {o.avg_rating}</> : "no feedback yet"} />
      </div>

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Incidents created vs resolved (14 days)">
            {trends.data ? <TrendChart points={trends.data} /> : <Spinner />}
          </Card>
          <Card title="SLA risk (likely to breach)" 
                actions={<Link className="link text-sm" to="/admin/sla">SLA report →</Link>}>
            {risks.data?.length === 0 && <p className="text-sm text-slate-500">Nothing at risk right now.</p>}
            {risks.data && risks.data.length > 0 && (
              <table className="data-table">
                <thead><tr><th>Incident</th><th>Priority</th><th>Risk</th><th>Target</th><th>Why</th></tr></thead>
                <tbody>
                  {risks.data.slice(0, 8).map((r) => (
                    <tr key={r.incident_id}>
                      <td>
                        <Link className="link font-mono text-xs" to={`/incidents/${r.incident_id}`}>{r.number}</Link>
                        <div className="text-slate-800">{r.title}</div>
                      </td>
                      <td><PriorityBadge priority={r.priority} /></td>
                      <td><RiskBadge level={r.level} /><div className="text-xs text-slate-400">score {r.risk_score}</div></td>
                      <td className="text-xs whitespace-nowrap">
                        {r.target.toLowerCase()}<br />
                        {r.minutes_left >= 0 ? `${formatMinutes(r.minutes_left)} left` : <span className="text-rose-600">{formatMinutes(-r.minutes_left)} over</span>}
                      </td>
                      <td className="text-xs text-slate-500">{r.reasons.join(" · ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>
        <div className="space-y-6">
          <Card title="Open incidents by priority">
            <BarList items={ALL_PRIORITIES.map((p) => ({
              label: PRIORITY_LABEL[p], value: o.by_priority_open[p] ?? 0,
              colour: p === "P1" ? "bg-rose-500" : p === "P2" ? "bg-orange-400" : p === "P3" ? "bg-yellow-400" : "bg-slate-400",
            }))} />
            <h3 className="mt-6 mb-3">By status</h3>
            <BarList items={Object.entries(o.by_status).map(([s, v]) => ({ label: STATUS_LABEL[s as keyof typeof STATUS_LABEL], value: v ?? 0 }))} />
          </Card>
          <LiveFeed />
        </div>
      </div>

      <Card title="Unassigned incidents" className="mt-6"
            actions={<Link className="link text-sm" to="/incidents?unassigned=true&open_only=true">View all →</Link>}>
        {unassigned.data ? (
          <IncidentTable incidents={unassigned.data.items} columns={["service", "reporter", "due"]} empty="Every open incident has a technician" />
        ) : <Spinner />}
      </Card>
    </>
  );
}
