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
                <td className="max-w-md min-w-56">
                  <div className="flex items-center gap-2">
                    <span className="mono text-faint">{i.number}</span>
                    <EscalationBadge level={i.escalation_level} />
                  </div>
                  <a
                    href={`/incidents/${i.id}`}
                    onClick={(e) => e.preventDefault()}
                    className="font-medium text-fg hover:text-brand"
                  >
                    {i.title}
                  </a>
                  {i.category && <div className="text-[12px] text-muted">{i.category.name}</div>}
                </td>
                <td><PriorityBadge priority={i.priority} /></td>
                <td><StatusBadge status={i.status} /></td>
                <td><SlaBadge status={i.sla_status} /></td>
                {show("service") && <td className="text-muted">{i.service?.name}</td>}
                {show("reporter") && <td className="text-muted">{i.reporter?.name}</td>}
                {show("technician") && (
                  <td className="text-muted">{i.technician?.name ?? <span className="font-medium text-warning">Unassigned</span>}</td>
                )}
                {show("due") && (
                  <td>
                    <DueIn due={waitingForResponse ? i.response_due_at : i.resolution_due_at}
                           done={!open || i.status === "PENDING_INFO"} />
                  </td>
                )}
                <td className="text-[12.5px] whitespace-nowrap text-muted tabular-nums">{relativeTime(i.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
