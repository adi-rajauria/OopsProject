import { useNavigate } from "react-router";
import type { IncidentSummary } from "../api/types";
import { relativeTime } from "../lib/format";
import { EscalationBadge, PriorityBadge, SlaBadge, StatusBadge } from "./badges";
import { DueIn } from "./SlaPanel";
import { EmptyState } from "./ui";

type Column = "reporter" | "technician" | "service" | "due";

export function IncidentTable({ incidents, columns = ["service", "technician", "due"], empty = "No incidents found" }: {
  incidents: IncidentSummary[];
  columns?: Column[];
  empty?: string;
}) {
  const navigate = useNavigate();
  if (incidents.length === 0) return <EmptyState title={empty} />;
  const show = (c: Column) => columns.includes(c);

  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>Incident</th>
            <th>Priority</th>
            <th>Status</th>
            <th>SLA</th>
            {show("service") && <th>Service</th>}
            {show("reporter") && <th>Reporter</th>}
            {show("technician") && <th>Technician</th>}
            {show("due") && <th>Next deadline</th>}
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((i) => {
            const waitingForResponse = ["CLASSIFIED", "ASSIGNED"].includes(i.status);
            const open = !["RESOLVED", "VERIFIED", "CLOSED"].includes(i.status);
            return (
              <tr key={i.id} className="cursor-pointer" onClick={() => navigate(`/incidents/${i.id}`)}>
                <td className="max-w-md">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-500">{i.number}</span>
                    <EscalationBadge level={i.escalation_level} />
                  </div>
                  <a
                    href={`/incidents/${i.id}`}
                    onClick={(e) => e.preventDefault()}
                    className="font-medium text-slate-900 hover:text-[var(--accent)]"
                  >
                    {i.title}
                  </a>
                  {i.category && <div className="text-xs text-slate-500">{i.category.name}</div>}
                </td>
                <td><PriorityBadge priority={i.priority} /></td>
                <td><StatusBadge status={i.status} /></td>
                <td><SlaBadge status={i.sla_status} /></td>
                {show("service") && <td className="text-slate-600">{i.service?.name}</td>}
                {show("reporter") && <td className="text-slate-600">{i.reporter?.name}</td>}
                {show("technician") && (
                  <td className="text-slate-600">{i.technician?.name ?? <span className="text-amber-700">Unassigned</span>}</td>
                )}
                {show("due") && (
                  <td>
                    <DueIn due={waitingForResponse ? i.response_due_at : i.resolution_due_at}
                           done={!open || i.status === "PENDING_INFO"} />
                  </td>
                )}
                <td className="whitespace-nowrap text-slate-500">{relativeTime(i.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
