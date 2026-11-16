import { Link } from "react-router";
import { technicianApi } from "../../api/endpoints";
import { useUser } from "../../auth/AuthContext";
import { BarList, UtilisationBar } from "../../components/charts";
import { Card, ErrorMessage, PageHeader, Spinner } from "../../components/ui";
import { useLiveRefresh } from "../../hooks/LiveEvents";
import { useAsync } from "../../hooks/useAsync";

/** Technician workload report (spec dashboard #2). Shared by technicians and administrators. */
export function WorkloadPage() {
  const user = useUser();
  const stats = useAsync(() => technicianApi.workload(), []);
  useLiveRefresh(() => stats.reload());
  if (stats.error) return <ErrorMessage error={stats.error} onRetry={stats.reload} />;
  if (!stats.data) return <Spinner />;
  const teams = [...new Set(stats.data.map((t) => t.team))].sort();

  return (
    <>
      <PageHeader title="Technician workload" subtitle="Active incidents against each technician's workload limit, plus resolution performance." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Active incidents per technician" className="lg:col-span-1">
          <BarList items={stats.data.map((t) => ({
            label: t.name,
            value: t.active,
            colour: t.utilisation_pct >= 100 ? "bg-rose-500" : t.utilisation_pct >= 75 ? "bg-amber-500" : undefined,
          }))} />
        </Card>
        <Card title="Details" className="lg:col-span-2">
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Technician</th>
                  <th>Team</th>
                  <th>Load</th>
                  <th>Resolved</th>
                  <th>Avg. resolution</th>
                  <th>Rating</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {teams.flatMap((team) =>
                  stats.data!.filter((t) => t.team === team).map((t) => (
                    <tr key={t.technician_id} className={t.technician_id === user.id ? "bg-[var(--accent-soft)]/40" : ""}>
                      <td>
                        <Link className="font-medium text-slate-800 hover:text-[var(--accent)]" to={`/incidents?technician_id=${t.technician_id}&open_only=true`}>
                          {t.name}
                        </Link>
                        <span className="ml-1 text-xs text-slate-400">{t.code}{t.is_team_lead ? " · lead" : ""}</span>
                      </td>
                      <td className="text-slate-600">{t.team}</td>
                      <td><UtilisationBar active={t.active} max={t.max_workload} /></td>
                      <td className="tabular-nums">{t.resolved_total}</td>
                      <td className="tabular-nums">{t.avg_resolution_hours !== null ? `${t.avg_resolution_hours} h` : "—"}</td>
                      <td className="tabular-nums">{t.avg_rating !== null ? `${t.avg_rating} ★` : "—"}</td>
                      <td>{t.is_available ? <span className="text-emerald-700">Available</span> : <span className="text-slate-400">Away</span>}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}
