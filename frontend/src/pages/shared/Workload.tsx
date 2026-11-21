import { Link } from "react-router";
import { technicianApi } from "../../api/endpoints";
import { useUser } from "../../auth/AuthContext";
import { BarList, UtilisationBar, utilisationColour } from "../../components/charts";
import { StarIcon } from "../../components/icons";
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
      <div className="grid items-start gap-6 lg:grid-cols-3">
        <Card title="Active incidents per technician" className="lg:col-span-1">
          <BarList items={stats.data.map((t) => ({
            label: t.name,
            value: t.active,
            colour: t.utilisation_pct >= 75 ? utilisationColour(t.utilisation_pct) : undefined,
          }))} />
        </Card>
        <Card title="Details" flush className="lg:col-span-2">
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
                    <tr key={t.technician_id} className={t.technician_id === user.id ? "bg-brand-soft/40" : ""}>
                      <td>
                        <Link className="font-medium text-fg hover:text-brand" to={`/incidents?technician_id=${t.technician_id}&open_only=true`}>
                          {t.name}
                        </Link>
                        <span className="ml-1 text-xs text-faint">{t.code}{t.is_team_lead ? " · lead" : ""}</span>
                      </td>
                      <td className="text-muted">{t.team}</td>
                      <td><UtilisationBar active={t.active} max={t.max_workload} /></td>
                      <td className="tabular-nums">{t.resolved_total}</td>
                      <td className="tabular-nums">{t.avg_resolution_hours !== null ? `${t.avg_resolution_hours} h` : "—"}</td>
                      <td className="tabular-nums whitespace-nowrap">{t.avg_rating !== null ? <span className="inline-flex items-center gap-1">{t.avg_rating}<StarIcon size={12} filled className="text-warning-solid" /></span> : "—"}</td>
                      <td>{t.is_available ? <span className="text-ok">Available</span> : <span className="text-faint">Away</span>}</td>
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
