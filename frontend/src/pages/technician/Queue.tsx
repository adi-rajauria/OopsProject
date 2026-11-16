import { useState } from "react";
import { Link } from "react-router";
import { incidentsApi, intelligenceApi, technicianApi } from "../../api/endpoints";
import type { IncidentSummary } from "../../api/types";
import { useAuth, useUser } from "../../auth/AuthContext";
import { EscalationBadge, PriorityBadge, RiskBadge, SlaBadge, StatusBadge } from "../../components/badges";
import { UtilisationBar } from "../../components/charts";
import { DueIn } from "../../components/SlaPanel";
import { useToast } from "../../components/Toasts";
import { Card, EmptyState, ErrorMessage, PageHeader, Spinner, StatCard } from "../../components/ui";
import { useLiveRefresh } from "../../hooks/LiveEvents";
import { useAsync } from "../../hooks/useAsync";
import { relativeTime } from "../../lib/format";

const NEXT_STEP: Partial<Record<IncidentSummary["status"], string>> = {
  ASSIGNED: "Acknowledge to stop the response clock",
  ACKNOWLEDGED: "Start the investigation",
  IN_PROGRESS: "Investigate and resolve",
  PENDING_INFO: "Waiting for the reporter (SLA paused)",
};

function QueueItem({ incident, onAcknowledge, busy }: { incident: IncidentSummary; onAcknowledge: () => void; busy: boolean }) {
  const waiting = incident.status === "ASSIGNED";
  return (
    <li className={`card px-4 py-3 ${incident.priority === "P1" ? "border-l-4 border-l-rose-500" : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-slate-500">{incident.number}</span>
            <PriorityBadge priority={incident.priority} />
            <StatusBadge status={incident.status} />
            <SlaBadge status={incident.sla_status} />
            <EscalationBadge level={incident.escalation_level} />
          </div>
          <Link to={`/incidents/${incident.id}`} className="mt-1 block font-medium text-slate-900 hover:text-[var(--accent)]">
            {incident.title}
          </Link>
          <p className="text-xs text-slate-500">
            {incident.service?.name} · {incident.category?.name} · reported by {incident.reporter?.name} {relativeTime(incident.created_at)}
          </p>
          <p className="mt-1 text-xs font-medium text-slate-600">{NEXT_STEP[incident.status]}</p>
        </div>
        <div className="flex flex-col items-end gap-2 text-sm">
          <span className="text-xs text-slate-500">{waiting ? "Response due" : "Resolution due"}</span>
          <DueIn due={waiting ? incident.response_due_at : incident.resolution_due_at} done={incident.status === "PENDING_INFO"} />
          {waiting ? (
            <button className="btn-primary btn-sm" disabled={busy} onClick={onAcknowledge}>Acknowledge</button>
          ) : (
            <Link className="btn-secondary btn-sm" to={`/incidents/${incident.id}`}>Open</Link>
          )}
        </div>
      </div>
    </li>
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
        subtitle={`Skills: ${profile.skills.join(", ") || "none"} · ${profile.team} team${profile.is_team_lead ? " (team lead)" : ""}`}
        actions={
          <button className={profile.is_available ? "btn-secondary" : "btn-primary"} onClick={toggleAvailability}>
            {profile.is_available ? "● Available - go unavailable" : "○ Unavailable - become available"}
          </button>
        }
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Active incidents" value={items.length} hint={<UtilisationBar active={items.length} max={profile.max_workload} />} />
        <StatCard label="Waiting for acknowledgement" value={items.filter((i) => i.status === "ASSIGNED").length}
                  tone={items.some((i) => i.status === "ASSIGNED") ? "warning" : "default"} />
        <StatCard label="Critical (P1)" value={items.filter((i) => i.priority === "P1").length}
                  tone={items.some((i) => i.priority === "P1") ? "danger" : "default"} />
        <StatCard label="SLA breached / at high risk" value={myRisks.length} tone={myRisks.length ? "danger" : "success"} />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {queue.error && <ErrorMessage error={queue.error} onRetry={queue.reload} />}
          {queue.loading && !queue.data && <Spinner />}
          {queue.data && items.length === 0 && <EmptyState title="Your queue is empty">New assignments appear here instantly.</EmptyState>}
          <ul className="space-y-3">
            {items.map((i) => <QueueItem key={i.id} incident={i} busy={busy} onAcknowledge={() => acknowledge(i)} />)}
          </ul>
        </div>
        <Card title="Needs attention across the team" className="h-fit">
          {risks.data?.length === 0 && <p className="text-sm text-slate-500">No incidents at high SLA risk.</p>}
          <ul className="space-y-3">
            {risks.data?.slice(0, 8).map((r) => (
              <li key={r.incident_id} className="text-sm">
                <div className="flex items-center justify-between gap-2">
                  <Link className="link font-mono text-xs" to={`/incidents/${r.incident_id}`}>{r.number}</Link>
                  <RiskBadge level={r.level} />
                </div>
                <p className="text-slate-700">{r.title}</p>
                <p className="text-xs text-slate-500">{r.reasons.join(" · ")}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
