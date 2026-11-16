import type { IncidentStatus, Priority, Role, SLAStatus } from "../api/types";

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const timeOnly = new Intl.DateTimeFormat(undefined, { timeStyle: "short" });

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : "—";
}

export function formatTime(iso: string): string {
  return timeOnly.format(new Date(iso));
}

/** "3 min ago", "in 2 h 5 min" */
export function relativeTime(iso: string, now = Date.now()): string {
  const diffMin = Math.round((new Date(iso).getTime() - now) / 60000);
  const text = formatMinutes(Math.abs(diffMin));
  if (Math.abs(diffMin) < 1) return "just now";
  return diffMin < 0 ? `${text} ago` : `in ${text}`;
}

export function formatMinutes(minutes: number): string {
  const m = Math.round(minutes);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  if (h < 48) return m % 60 ? `${h} h ${m % 60} min` : `${h} h`;
  const d = Math.floor(h / 24);
  return h % 24 ? `${d} d ${h % 24} h` : `${d} d`;
}

export function titleCase(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export const STATUS_LABEL: Record<IncidentStatus, string> = {
  NEW: "New",
  CLASSIFIED: "Classified",
  ASSIGNED: "Assigned",
  ACKNOWLEDGED: "Acknowledged",
  IN_PROGRESS: "In progress",
  PENDING_INFO: "Waiting for info",
  RESOLVED: "Resolved",
  VERIFIED: "Verified",
  CLOSED: "Closed",
};

export const PRIORITY_LABEL: Record<Priority, string> = {
  P1: "P1 · Critical",
  P2: "P2 · High",
  P3: "P3 · Medium",
  P4: "P4 · Low",
};

export const SLA_LABEL: Record<SLAStatus, string> = {
  ON_TRACK: "On track",
  AT_RISK: "At risk",
  BREACHED: "Breached",
  PAUSED: "Paused",
  MET: "Met",
};

export const ROLE_LABEL: Record<Role, string> = {
  EMPLOYEE: "Employee",
  TECHNICIAN: "Technician",
  ADMINISTRATOR: "Administrator",
};

export const IMPACT_OPTIONS = [
  { value: 1, label: "Just me", hint: "Only my work is affected" },
  { value: 2, label: "My team", hint: "A few colleagues are affected" },
  { value: 3, label: "Department", hint: "A whole department or site" },
  { value: 4, label: "Organisation", hint: "Customers or the whole company" },
];

export const URGENCY_OPTIONS = [
  { value: 1, label: "Can wait", hint: "Workaround available" },
  { value: 2, label: "Soon", hint: "Slows work down" },
  { value: 3, label: "Urgent", hint: "Important work is blocked" },
  { value: 4, label: "Critical", hint: "Business stopped / money lost" },
];

/** Mirrors Incident.number_for() in the backend. */
export const incidentNumber = (id: number) => `INC${1000 + id}`;

export const OPEN_STATUSES: IncidentStatus[] = [
  "NEW",
  "CLASSIFIED",
  "ASSIGNED",
  "ACKNOWLEDGED",
  "IN_PROGRESS",
  "PENDING_INFO",
];
