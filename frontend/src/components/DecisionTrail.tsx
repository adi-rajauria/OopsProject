import type { ReactNode } from "react";
import type { AuditRecord, IncidentDetail } from "../api/types";
import { formatMinutes, PRIORITY_LABEL } from "../lib/format";
import { Card, Spinner } from "./ui";

/**
 * "Why Decerno decided": every automatic decision on one incident, each with the reason the system recorded for it.
 *
 * Built from the incident and its audit trail only (the services already record a reason with every decision),
 * so it explains exactly what happened rather than re-computing it in the browser.
 */
export function DecisionTrail({ incident: i, audit }: { incident: IncidentDetail; audit: AuditRecord[] | undefined }) {
  return (
    <Card
      title={
        <div className="py-0.5">
          <h2 className="text-[13.5px]">Why Decerno decided</h2>
          <p className="text-[12px] text-muted">Every automatic decision on this incident, with its reason.</p>
        </div>
      }
    >
      {audit ? <Decisions incident={i} audit={audit} /> : <Spinner />}
    </Card>
  );
}

function Decisions({ incident: i, audit }: { incident: IncidentDetail; audit: AuditRecord[] }) {
  const last = (action: string) => [...audit].reverse().find((a) => a.action === action);
  const all = (action: string) => audit.filter((a) => a.action === action);

  const classified = last("CLASSIFIED");
  const calculated = last("PRIORITY_CALCULATED");
  const changed = last("PRIORITY_CHANGED");
  const assigned = last("ASSIGNED");
  const related = last("RELATED_DETECTED");
  const escalations = all("ESCALATED");

  const categoryNote = classified?.description.match(/\(([^)]*)\)\s*$/)?.[1];
  const priorityWhy = calculated?.description.replace(/^Priority calculated as \S+ \(score [^)]*\):\s*/, "");
  const assignWhy = assigned?.description.split(" - ").slice(1).join(" - ");
  const similarWhy = related?.description.replace(/^Similar incidents detected:\s*/, "");
  const foundAtReport = similarWhy ? similarWhy.split(";").length : 0;
  const linkedLater = Math.max(0, i.links.length - foundAtReport);
  const laterNote = linkedLater > 0
    ? ` ${linkedLater} later report${linkedLater > 1 ? "s were" : " was"} linked to this one as people reported the same problem.`
    : "";

  const rows: { label: string; value: ReactNode; why: ReactNode }[] = [
    {
      label: "Category",
      value: i.category?.name ?? "Not classified",
      why: categoryNote
        ? capitalise(categoryNote)
        : i.suggested_category && i.suggested_category.id === i.category?.id
          ? "Chosen by the reporter, and it matches the suggestion from keywords and similar past incidents"
          : "Chosen by the reporter",
    },
    {
      label: "Priority",
      value: i.priority ? PRIORITY_LABEL[i.priority] : "—",
      why: (
        <>
          {priorityWhy ? prettyFormula(priorityWhy) : "Impact × urgency × business criticality of the service"}
          {changed && <span className="block">Later: {changed.description.replace(/; SLA deadlines recalculated$/, "")}, deadlines recalculated.</span>}
        </>
      ),
    },
    {
      label: "Deadlines",
      value: i.sla
        ? `Respond within ${formatMinutes(i.sla.response_minutes)} · resolve within ${formatMinutes(i.sla.resolution_minutes)}`
        : "No SLA",
      why: i.sla ? (
        <>
          The {i.priority} SLA policy for {i.service?.name}; a warning is raised at {i.sla.warning_pct}% of the time.
          {i.sla.paused && " The clock is paused now, while waiting for the reporter."}
          {!i.sla.paused && i.sla.paused_seconds > 0 &&
            ` The clock was paused for ${formatMinutes(Math.round(i.sla.paused_seconds / 60))} while waiting for the reporter.`}
        </>
      ) : "",
    },
    {
      label: "Technician",
      value: i.technician?.name ?? "Waiting for an administrator",
      why: assignWhy
        ? capitalise(assignWhy)
        : i.technician
          ? "Assigned by an administrator"
          : "No available technician had the skill or free capacity, so it was left for an administrator",
    },
    {
      label: "Similar reports",
      value: i.links.length ? `${i.links.length} linked` : "None",
      why: (similarWhy
        ? "When reported: " + similarWhy.replace(/\((0\.\d+|1\.0+)\)/g, (_, s) => `(${Math.round(Number(s) * 100)}% similar)`) + "."
        : `When reported, no open incident on ${i.service?.name ?? "this service"} from the last 24 hours was similar enough.`)
        + laterNote,
    },
  ];
  if (escalations.length > 0) {
    const levels = escalations.map((e) => e.description.match(/\(([^)]*)\)/)?.[1]).filter(Boolean);
    rows.push({
      label: "Escalation",
      value: `Level ${i.escalation_level || escalations.length} · ${levels[levels.length - 1] ?? ""}`,
      why: `Not acknowledged within the response window, so it moved up the chain: ${levels.join(" → ")}`,
    });
  }

  return (
    <dl className="divide-y divide-line">
      {rows.map((r) => (
        <div key={r.label} className="grid gap-x-4 gap-y-0.5 py-2.5 first:pt-0 last:pb-0 sm:grid-cols-[120px_minmax(0,1fr)]">
          <dt className="text-[12px] font-medium tracking-wide text-muted uppercase sm:pt-px">{r.label}</dt>
          <dd>
            <div className="text-[13.5px] font-medium text-fg">{r.value}</div>
            {r.why && <div className="mt-0.5 text-[12.5px] text-muted">{r.why}</div>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** "impact 4 x urgency 4 x criticality 4 = 64; x1.5 for 500 affected user(s) -> 64.0 => P1 (Critical)" made readable. */
const prettyFormula = (s: string) =>
  capitalise(
    s.replace(/ x /g, " × ").replace(/\bx(\d)/g, "×$1").replace(/\s*=>\s*/g, " → ").replace(/\s*->\s*/g, " → ")
      .replace(/(\d+)\.0\b/g, "$1"),
  );
