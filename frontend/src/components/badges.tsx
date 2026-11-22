import type { IncidentStatus, Priority, RiskLevel, Role, SLAStatus } from "../api/types";
import { PRIORITY_LABEL, ROLE_LABEL, SLA_LABEL, STATUS_LABEL } from "../lib/format";
import { AlertIcon, CheckIcon, ChevronUpIcon, PauseIcon } from "./icons";

/*
 * Status language: colour only where it carries meaning.
 *  - priority: a square mono tag (P1 is the only solid one)
 *  - status: a dot + the state name; nine states share five tones ("who has the ball")
 *  - SLA / risk: quiet text when fine, coloured tag only when someone should act
 */

function Tag({ className, children, title }: { className: string; children: React.ReactNode; title?: string }) {
  return (
    <span title={title}
          className={`inline-flex h-5 items-center gap-1 rounded-[3px] px-1.5 text-[11.5px] leading-none font-medium whitespace-nowrap ${className}`}>
      {children}
    </span>
  );
}

const STATUS_TONE: Record<IncidentStatus, string> = {
  NEW: "bg-faint",
  CLASSIFIED: "bg-faint",
  ASSIGNED: "bg-faint",
  ACKNOWLEDGED: "bg-brand",
  IN_PROGRESS: "bg-brand",
  PENDING_INFO: "bg-warning-solid",
  RESOLVED: "bg-ok-solid",
  VERIFIED: "bg-ok-solid",
  CLOSED: "border border-faint bg-transparent",
};

export function StatusBadge({ status }: { status: IncidentStatus }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-[13px] whitespace-nowrap ${status === "CLOSED" ? "text-muted" : "text-fg"}`}>
      <span aria-hidden className={`h-1.5 w-1.5 shrink-0 rounded-full ${STATUS_TONE[status]}`} />
      {STATUS_LABEL[status]}
    </span>
  );
}

const PRIORITY_STYLES: Record<Priority, string> = {
  P1: "bg-critical-solid text-white",
  P2: "bg-critical-soft text-critical",
  P3: "bg-warning-soft text-warning",
  P4: "bg-sunken text-muted",
};

export function PriorityBadge({ priority, long = false }: { priority: Priority | null; long?: boolean }) {
  if (!priority) return <span className="text-faint">—</span>;
  return (
    <Tag className={`font-mono ${PRIORITY_STYLES[priority]}`} title={PRIORITY_LABEL[priority]}>
      {long ? PRIORITY_LABEL[priority] : priority}
    </Tag>
  );
}

export function SlaBadge({ status }: { status: SLAStatus | null }) {
  if (!status) return <span className="text-faint">—</span>;
  const label = SLA_LABEL[status];
  switch (status) {
    case "BREACHED":
      return <Tag className="bg-critical-soft text-critical"><AlertIcon size={12} />{label}</Tag>;
    case "AT_RISK":
      return <Tag className="bg-warning-soft text-warning"><AlertIcon size={12} />{label}</Tag>;
    case "PAUSED":
      return <span className="inline-flex items-center gap-1 text-[13px] whitespace-nowrap text-muted"><PauseIcon size={12} />{label}</span>;
    case "MET":
      return <span className="inline-flex items-center gap-1 text-[13px] whitespace-nowrap text-ok"><CheckIcon size={12} />{label}</span>;
    default:
      return <span className="text-[13px] whitespace-nowrap text-muted">{label}</span>;
  }
}

const RISK_STYLES: Record<RiskLevel, string> = {
  LOW: "bg-sunken text-muted",
  MEDIUM: "bg-warning-soft text-warning",
  HIGH: "bg-critical-soft text-critical",
  BREACHED: "bg-critical-solid text-white",
};

export function RiskBadge({ level }: { level: RiskLevel }) {
  return <Tag className={RISK_STYLES[level]}>{level === "BREACHED" ? "Breached" : `${level.charAt(0)}${level.slice(1).toLowerCase()} risk`}</Tag>;
}

/** Role marker: neutral on purpose - the brand colour is shared, the role is named. */
export function RoleBadge({ role }: { role: Role }) {
  return <Tag className="border border-line-strong text-muted">{ROLE_LABEL[role]}</Tag>;
}

const ESCALATION_NAMES = ["", "Technician", "Team Lead", "System Admin", "IT Manager"];

export function EscalationBadge({ level }: { level: number }) {
  if (level <= 0) return null;
  return (
    <Tag className="border border-critical/40 text-critical" title={`Escalated to level ${level}`}>
      <ChevronUpIcon size={12} strokeWidth={2} />
      L{level} {ESCALATION_NAMES[level] ?? ""}
    </Tag>
  );
}
