import type { SLAInfo } from "../api/types";
import { useNow } from "../hooks/useAsync";
import { formatDateTime, formatMinutes } from "../lib/format";
import { SlaBadge } from "./badges";

/** A compact countdown for tables: "12 min left" / "overdue 5 min". */
export function DueIn({ due, done = false }: { due: string | null; done?: boolean }) {
  const now = useNow();
  if (!due || done) return <span className="text-slate-400">—</span>;
  const minutes = Math.round((new Date(due).getTime() - now) / 60000);
  return minutes >= 0 ? (
    <span className="whitespace-nowrap text-slate-600 tabular-nums">{formatMinutes(minutes)} left</span>
  ) : (
    <span className="font-medium whitespace-nowrap text-rose-600 tabular-nums">overdue {formatMinutes(-minutes)}</span>
  );
}

interface TargetProps {
  label: string;
  startMs: number;
  targetMinutes: number;
  due: string;
  metAt: string | null;
  breached: boolean;
  pausedMs: number;
  paused: boolean;
  warningPct: number;
  now: number;
}

function Target({ label, startMs, targetMinutes, due, metAt, breached, pausedMs, paused, warningPct, now }: TargetProps) {
  const endMs = metAt ? new Date(metAt).getTime() : now;
  const pct = Math.max(0, Math.round((100 * (endMs - startMs - pausedMs)) / (targetMinutes * 60_000)));
  const remaining = Math.round((new Date(due).getTime() - now) / 60000);
  const overdue = breached || (!metAt && !paused && remaining < 0);

  let state: string;
  if (metAt) state = `${breached ? "met late" : "met"} · ${formatDateTime(metAt)}`;
  else if (paused) state = "paused - waiting for the reporter";
  else state = remaining >= 0 ? `${formatMinutes(remaining)} left` : `overdue by ${formatMinutes(-remaining)}`;

  const colour = paused && !metAt ? "bg-slate-400" : overdue || pct >= 100 ? "bg-rose-500" : pct >= warningPct ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium text-slate-700">
          {label} <span className="font-normal text-slate-500">({formatMinutes(targetMinutes)} target)</span>
        </span>
        <span className={overdue ? "font-medium text-rose-600" : "text-slate-500"}>{state}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100" role="meter" aria-valuenow={Math.min(pct, 100)} aria-label={`${label} time used`}>
        <div className={`h-full rounded-full ${colour}`} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <p className="mt-1 text-xs text-slate-500">Due {formatDateTime(due)}</p>
    </div>
  );
}

export function SlaPanel({ sla }: { sla: SLAInfo }) {
  const now = useNow(15_000);
  // Both clocks start when the incident was created; only the resolution clock is paused in PENDING_INFO.
  const startMs = new Date(sla.response_due_at).getTime() - sla.response_minutes * 60_000;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3>Service level</h3>
        <SlaBadge status={sla.status} />
      </div>
      <Target label="Response" startMs={startMs} targetMinutes={sla.response_minutes} due={sla.response_due_at}
              metAt={sla.responded_at} breached={sla.response_breached} pausedMs={0} paused={false}
              warningPct={sla.warning_pct} now={now} />
      <Target label="Resolution" startMs={startMs} targetMinutes={sla.resolution_minutes} due={sla.resolution_due_at}
              metAt={sla.resolved_at} breached={sla.resolution_breached} pausedMs={sla.paused_seconds * 1000}
              paused={sla.paused} warningPct={sla.warning_pct} now={now} />
      {sla.paused_seconds > 0 && (
        <p className="text-xs text-slate-500">
          The clock was paused for {formatMinutes(sla.paused_seconds / 60)} while waiting for information, so the
          resolution deadline moved later by the same amount.
        </p>
      )}
    </div>
  );
}
