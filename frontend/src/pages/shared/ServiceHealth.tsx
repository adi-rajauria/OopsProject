import { Link, useNavigate } from "react-router";
import { intelligenceApi, reportsApi } from "../../api/endpoints";
import { useUser } from "../../auth/AuthContext";
import { BarList } from "../../components/charts";
import { DependencyGraph } from "../../components/DependencyGraph";
import { Card, ErrorMessage, PageHeader, Spinner } from "../../components/ui";
import { useLiveRefresh } from "../../hooks/LiveEvents";
import { useAsync } from "../../hooks/useAsync";
import { incidentNumber } from "../../lib/format";

/** Service dependency graph + correlation (innovation) and, for admins, the service analysis report. */
export function ServiceHealthPage() {
  const user = useUser();
  const navigate = useNavigate();
  const admin = user.role === "ADMINISTRATOR";
  const correlation = useAsync(() => intelligenceApi.correlation(), []);
  const analysis = useAsync(() => (admin ? reportsApi.services() : Promise.resolve([])), [admin]);
  useLiveRefresh(() => {
    correlation.reload();
    analysis.reload();
  });

  if (correlation.error) return <ErrorMessage error={correlation.error} onRetry={correlation.reload} />;
  if (!correlation.data) return <Spinner />;
  const report = correlation.data;

  return (
    <>
      <PageHeader title="Service health & correlation"
                  subtitle="Arrows point from a service to what it depends on. Red = hotspot (3+ incidents in 2 h), amber = open incidents." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Dependency graph" className="lg:col-span-2">
          <DependencyGraph report={report} onSelect={(id) => navigate(`/incidents?service_id=${id}&open_only=true`)} />
          <p className="hint">Click a service to see its open incidents.</p>
        </Card>
        <Card title="Likely common causes" className="h-fit">
          {report.findings.length === 0 && <p className="text-sm text-slate-500">No correlated incidents right now.</p>}
          <ul className="space-y-4">
            {report.findings.map((f) => (
              <li key={`${f.kind}-${f.root_service_id}`} className="text-sm">
                <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${f.kind === "HOTSPOT" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-800"}`}>
                  {f.kind === "HOTSPOT" ? "Hotspot" : "Upstream cause"}
                </span>
                <p className="mt-1 text-slate-800">{f.explanation}</p>
                <p className="mt-1 flex flex-wrap gap-x-2 text-xs">
                  {f.incident_ids.map((id) => (
                    <Link key={id} className="link font-mono" to={`/incidents/${id}`}>{incidentNumber(id)}</Link>
                  ))}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {admin && analysis.data && (
        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <Card title="Incidents per service">
            <BarList items={analysis.data.map((s) => ({ label: s.name, value: s.total }))} />
          </Card>
          <Card title="Service analysis" className="lg:col-span-2">
            <table className="data-table">
              <thead>
                <tr><th>Service</th><th>Criticality</th><th>Total</th><th>Open</th><th>SLA violations</th><th>MTTR</th></tr>
              </thead>
              <tbody>
                {analysis.data.map((s) => (
                  <tr key={s.service_id}>
                    <td><Link className="font-medium hover:text-[var(--accent)]" to={`/incidents?service_id=${s.service_id}`}>{s.name}</Link></td>
                    <td>{"●".repeat(s.criticality)}<span className="text-slate-300">{"●".repeat(4 - s.criticality)}</span></td>
                    <td className="tabular-nums">{s.total}</td>
                    <td className="tabular-nums">{s.open}</td>
                    <td className={`tabular-nums ${s.violations ? "font-medium text-rose-600" : ""}`}>{s.violations}</td>
                    <td className="tabular-nums">{s.mttr_hours !== null ? `${s.mttr_hours} h` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}
    </>
  );
}
