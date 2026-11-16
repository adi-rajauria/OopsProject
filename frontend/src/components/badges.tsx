import type { IncidentStatus, Priority, RiskLevel, Role, SLAStatus } from "../api/types";
import { PRIORITY_LABEL, ROLE_LABEL, SLA_LABEL, STATUS_LABEL } from "../lib/format";

function Pill({ className, children, title }: { className: string; children: React.ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset ${className}`}
    >
      {children}
    </span>
  );
}

const STATUS_STYLES: Record<IncidentStatus, string> = {
  NEW: "bg-slate-100 text-slate-700 ring-slate-200",
  CLASSIFIED: "bg-slate-100 text-slate-700 ring-slate-300",
  ASSIGNED: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  ACKNOWLEDGED: "bg-sky-50 text-sky-700 ring-sky-200",
  IN_PROGRESS: "bg-blue-50 text-blue-700 ring-blue-200",
  PENDING_INFO: "bg-amber-50 text-amber-800 ring-amber-200",
  RESOLVED: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  VERIFIED: "bg-teal-50 text-teal-700 ring-teal-200",
  CLOSED: "bg-slate-200 text-slate-600 ring-slate-300",
};

export function StatusBadge({ status }: { status: IncidentStatus }) {
  return <Pill className={STATUS_STYLES[status]}>{STATUS_LABEL[status]}</Pill>;
}

const PRIORITY_STYLES: Record<Priority, string> = {
  P1: "bg-rose-600 text-white ring-rose-600",
  P2: "bg-orange-100 text-orange-800 ring-orange-200",
  P3: "bg-yellow-50 text-yellow-800 ring-yellow-200",
  P4: "bg-slate-100 text-slate-600 ring-slate-200",
};

export function PriorityBadge({ priority, long = false }: { priority: Priority | null; long?: boolean }) {
  if (!priority) return <span className="text-slate-400">—</span>;
  return (
    <Pill className={PRIORITY_STYLES[priority]} title={PRIORITY_LABEL[priority]}>
      {long ? PRIORITY_LABEL[priority] : priority}
    </Pill>
  );
}

const SLA_STYLES: Record<SLAStatus, string> = {
  ON_TRACK: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  AT_RISK: "bg-amber-50 text-amber-800 ring-amber-300",
  BREACHED: "bg-rose-50 text-rose-700 ring-rose-300",
  PAUSED: "bg-slate-100 text-slate-600 ring-slate-300",
  MET: "bg-teal-50 text-teal-700 ring-teal-200",
};

export function SlaBadge({ status }: { status: SLAStatus | null }) {
  if (!status) return <span className="text-slate-400">—</span>;
  const icon = status === "BREACHED" ? "●" : status === "AT_RISK" ? "▲" : status === "PAUSED" ? "❚❚" : "";
  return (
    <Pill className={SLA_STYLES[status]}>
      {icon && <span aria-hidden>{icon}</span>}
      {SLA_LABEL[status]}
    </Pill>
  );
}

const RISK_STYLES: Record<RiskLevel, string> = {
  LOW: "bg-slate-100 text-slate-600 ring-slate-200",
  MEDIUM: "bg-amber-50 text-amber-800 ring-amber-200",
  HIGH: "bg-orange-100 text-orange-800 ring-orange-300",
  BREACHED: "bg-rose-600 text-white ring-rose-600",
};

export function RiskBadge({ level }: { level: RiskLevel }) {
  return <Pill className={RISK_STYLES[level]}>{level === "BREACHED" ? "Breached" : `${level.toLowerCase()} risk`}</Pill>;
}

const ROLE_STYLES: Record<Role, string> = {
  EMPLOYEE: "bg-sky-50 text-sky-700 ring-sky-200",
  TECHNICIAN: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  ADMINISTRATOR: "bg-violet-50 text-violet-700 ring-violet-200",
};

export function RoleBadge({ role }: { role: Role }) {
  return <Pill className={ROLE_STYLES[role]}>{ROLE_LABEL[role]}</Pill>;
}

export function EscalationBadge({ level }: { level: number }) {
  if (level <= 0) return null;
  const names = ["", "Technician", "Team Lead", "System Admin", "IT Manager"];
  return (
    <Pill className="bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-200" title="Escalation level">
      ⇧ L{level} {names[level] ?? ""}
    </Pill>
  );
}
