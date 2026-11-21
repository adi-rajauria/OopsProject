import type { AuditRecord } from "../api/types";
import { formatDateTime, titleCase } from "../lib/format";

/** Only events that change the picture get a colour; everything else is a neutral tick. */
const MARK: Record<string, string> = {
  CREATED: "bg-fg",
  RESOLVE: "bg-ok-solid",
  VERIFY: "bg-ok-solid",
  SLA_VIOLATED: "bg-critical-solid",
  ESCALATED: "bg-critical-solid",
  SLA_WARNING: "bg-warning-solid",
  REQUEST_INFO: "bg-warning-solid",
  REOPEN: "bg-warning-solid",
};

/** The incident's audit trail as a vertical timeline (spec: complete incident history). */
export function Timeline({ records }: { records: AuditRecord[] }) {
  return (
    <ol className="relative">
      {records.map((r, index) => (
        <li key={r.id ?? `${r.created_at}-${r.action}`} className="relative grid grid-cols-[14px_1fr] gap-x-3 pb-4 last:pb-0">
          {index < records.length - 1 && <span aria-hidden className="absolute top-3 bottom-0 left-[6px] w-px bg-line" />}
          <span aria-hidden className={`relative mt-1.5 h-[7px] w-[7px] justify-self-center rounded-full ring-4 ring-surface ${MARK[r.action] ?? "bg-line-strong"}`} />
          <div className="min-w-0">
            <div className="flex flex-wrap items-baseline gap-x-2 text-[12px] text-muted">
              <time className="font-mono text-[11.5px]" dateTime={r.created_at}>{formatDateTime(r.created_at)}</time>
              <span className="text-fg">{r.actor_name}</span>
              {r.new_state && r.previous_state !== r.new_state && (
                <span className="font-mono text-[11px] text-faint">
                  {r.previous_state ? `${r.previous_state} → ` : ""}
                  {r.new_state}
                </span>
              )}
            </div>
            <p className="text-[13px] text-fg">
              <span className="font-medium">{titleCase(r.action)}.</span> <span className="text-muted">{r.description}</span>
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
