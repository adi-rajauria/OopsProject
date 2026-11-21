import { useState } from "react";
import { Link } from "react-router";
import { incidentsApi, intelligenceApi, technicianApi } from "../../api/endpoints";
import type { IncidentSummary } from "../../api/types";
import { useAuth, useUser } from "../../auth/AuthContext";
import { EscalationBadge, PriorityBadge, RiskBadge, SlaBadge, StatusBadge } from "../../components/badges";
import { UtilisationBar } from "../../components/charts";
import { DueIn } from "../../components/SlaPanel";
import { useToast } from "../../components/Toasts";
import { Card, EmptyState, ErrorMessage, PageHeader, Spinner, Stat, StatStrip } from "../../components/ui";
import { useLiveRefresh } from "../../hooks/LiveEvents";
import { useAsync } from "../../hooks/useAsync";
import { relativeTime } from "../../lib/format";

const NEXT_STEP: Partial<Record<IncidentSummary["status"], string>> = {
  ASSIGNED: "Acknowledge to stop the response clock",
  ACKNOWLEDGED: "Start the investigation",
  IN_PROGRESS: "Investigate and resolve",
  PENDING_INFO: "Waiting for the reporter (SLA paused)",
};

const RAIL: Record<string, string> = {
  P1: "bg-critical-solid",
  P2: "bg-critical-solid/45",
  P3: "bg-warning-solid",
  P4: "bg-line-strong",
};

function QueueItem({ incident, onAcknowledge, busy }: { incident: IncidentSummary; onAcknowledge: () => void; busy: boolean }) {
  const waiting = incident.status === "ASSIGNED";
  return (
    <li className="relative grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 py-3 pr-4 pl-5 hover:bg-sunken/50">
      <span aria-hidden className={`absolute top-0 bottom-0 left-0 w-[3px] ${RAIL[incident.priority ?? "P4"]}`} />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="mono text-faint">{incident.number}</span>
          <PriorityBadge priority={incident.priority} />
          <StatusBadge status={incident.status} />
          <SlaBadge status={incident.sla_status} />
          <EscalationBadge level={incident.escalation_level} />
        </div>
        <Link to={`/incidents/${incident.id}`} className="mt-1 block text-[14px] font-medium text-fg hover:text-brand">
          {incident.title}
        </Link>
        <p className="text-[12px] text-muted">
          {incident.service?.name} · {incident.category?.name} · reported by {incident.reporter?.name} {relativeTime(incident.created_at)}
        </p>
        {NEXT_STEP[incident.status] && <p className="mt-1 text-[12.5px] text-fg">Next: {NEXT_STEP[incident.status]}</p>}
      </div>
      <div className="flex flex-col items-end gap-1.5 text-right">
        <span className="text-[11.5px] text-muted">{waiting ? "Response due" : "Resolution due"}</span>
        <DueIn due={waiting ? incident.response_due_at : incident.resolution_due_at} done={incident.status === "PENDING_INFO"} />
        {waiting ? (
          <button className="btn-primary btn-sm mt-1" disabled={busy} onClick={onAcknowledge}>Acknowledge</button>
        ) : (
          <Link className="btn-secondary btn-sm mt-1" to={`/incidents/${incident.id}`}>Open</Link>
        )}
      </div>
    </li>
  );
}

/** An on/off switch rather than a button whose label describes the opposite action. */
function AvailabilitySwitch({ available, onToggle }: { available: boolean; onToggle: () => void }) {
  return (
    <button role="switch" aria-checked={available} onClick={onToggle}
            className="flex items-center gap-2.5 rounded border border-line-strong bg-surface py-1.5 pr-3 pl-2 text-[13px] hover:bg-sunken">
      <span className={`relative h-4 w-7 rounded-full transition-colors ${available ? "bg-ok-solid" : "bg-line-strong"}`}>
        <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-surface transition-[left] ${available ? "left-3.5" : "left-0.5"}`} />
      </span>
      <span className="font-medium text-fg">{available ? "Available" : "Unavailable"}</span>
      <span className="hidden text-muted sm:inline">{available ? "for new assignments" : "no new assignments"}</span>
    </button>
  );
}

export function TechnicianQueuePage() {
  const user = useUser();
  const { setUser } = useAuth();
  const toast = useToast();
  const queue = useAsync(() => technicianApi.queue(), []);
  const risks = useAsync(() => intelligenceApi.slaRisk("HIGH"), []);
  const [busy, setBusy] = useState(false);
  useLiveRefresh(() => {
    queue.reload();
    risks.reload();
  });

  const profile = user.technician_profile!;
  const toggleAvailability = async () => {
    try {
      setUser(await technicianApi.setAvailability(!profile.is_available));
      toast.success(profile.is_available ? "You will not receive new assignments" : "You are available for new assignments");
    } catch (err) {
      toast.error(err);
    }
  };
  const acknowledge = async (incident: IncidentSummary) => {
    setBusy(true);
    try {
      await incidentsApi.acknowledge(incident.id);
      toast.success(`${incident.number} acknowledged`);
      queue.reload();
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };

  const items = queue.data ?? [];
  const myRisks = (risks.data ?? []).filter((r) => r.assigned_technician_id === user.id);
  return (
    <>
      <PageHeader
        title="My work queue"
        subtitle={`${profile.team} team${profile.is_team_lead ? " · team lead" : ""} · skills: ${profile.skills.join(", ") || "none"}`}
        actions={<AvailabilitySwitch available={profile.is_available} onToggle={toggleAvailability} />}
      />
      <div className="mb-6">
        <StatStrip columns={4}>
          <Stat label="Active incidents" value={items.length} hint={<UtilisationBar active={items.length} max={profile.max_workload} />} />
          <Stat label="Waiting for acknowledgement" value={items.filter((i) => i.status === "ASSIGNED").length}
                tone={items.some((i) => i.status === "ASSIGNED") ? "warning" : "default"} />
          <Stat label="Critical (P1)" value={items.filter((i) => i.priority === "P1").length}
                tone={items.some((i) => i.priority === "P1") ? "danger" : "default"} />
          <Stat label="SLA breached or high risk" value={myRisks.length} tone={myRisks.length ? "danger" : "success"} />
        </StatStrip>
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-3">
        <Card title="Assigned to me" flush className="lg:col-span-2"
              actions={<span className="text-muted">{items.length} active · highest priority first</span>}>
          {queue.error && <div className="p-4"><ErrorMessage error={queue.error} onRetry={queue.reload} /></div>}
          {queue.loading && !queue.data && <div className="px-4"><Spinner /></div>}
          {queue.data && items.length === 0 && <EmptyState title="Your queue is empty">New assignments appear here instantly.</EmptyState>}
          {items.length > 0 && (
            <ul className="divide-y divide-line">
              {items.map((i) => <QueueItem key={i.id} incident={i} busy={busy} onAcknowledge={() => acknowledge(i)} />)}
            </ul>
          )}
        </Card>
        <Card title="Needs attention across the team" flush>
          {risks.data?.length === 0 && <p className="p-4 text-[13px] text-muted">No incidents at high SLA risk.</p>}
          <ul className="divide-y divide-line">
            {risks.data?.slice(0, 8).map((r) => (
              <li key={r.incident_id} className="px-4 py-2.5 text-[13px]">
                <div className="flex items-center justify-between gap-2">
                  <Link className="link mono" to={`/incidents/${r.incident_id}`}>{r.number}</Link>
                  <RiskBadge level={r.level} />
                </div>
                <p className="mt-0.5 text-fg">{r.title}</p>
                <p className="text-[12px] text-muted">{r.reasons.join(" · ")}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
