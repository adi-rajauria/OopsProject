import type { AuditRecord } from "../api/types";
import { formatDateTime, titleCase } from "../lib/format";

const DOT: Record<string, string> = {
  CREATED: "bg-sky-500",
  ASSIGNED: "bg-indigo-500",
  RESOLVE: "bg-emerald-500",
  CLOSE: "bg-slate-500",
  SLA_VIOLATED: "bg-rose-500",
  SLA_WARNING: "bg-amber-500",
  ESCALATED: "bg-fuchsia-500",
  RELATED_DETECTED: "bg-violet-500",
};

/** The incident's audit trail as a vertical timeline (spec: complete incident history). */
export function Timeline({ records }: { records: AuditRecord[] }) {
  return (
    <ol className="relative space-y-4 border-l border-slate-200 pl-5">
      {records.map((r) => (
        <li key={r.id ?? `${r.created_at}-${r.action}`} className="relative">
          <span className={`absolute top-1.5 -left-[25px] h-2.5 w-2.5 rounded-full ring-4 ring-white ${DOT[r.action] ?? "bg-slate-300"}`} />
          <div className="flex flex-wrap items-baseline gap-x-2 text-xs text-slate-500">
            <time dateTime={r.created_at}>{formatDateTime(r.created_at)}</time>
            <span>·</span>
            <span className="font-medium text-slate-600">{r.actor_name}</span>
            {r.new_state && r.previous_state !== r.new_state && (
              <span className="rounded bg-slate-100 px-1.5 font-mono text-[11px]">
                {r.previous_state ? `${r.previous_state} → ` : ""}
                {r.new_state}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-800">
            <span className="font-medium">{titleCase(r.action)}</span> — {r.description}
          </p>
        </li>
      ))}
    </ol>
  );
}
