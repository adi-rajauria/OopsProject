import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import { incidentsApi, lookupsApi } from "../../api/endpoints";
import type { Comment, IncidentAction, IncidentDetail, User } from "../../api/types";
import { isStaff, useUser } from "../../auth/AuthContext";
import { EscalationBadge, PriorityBadge, StatusBadge } from "../../components/badges";
import { Stars } from "../../components/charts";
import { ArrowLeftIcon, StarIcon } from "../../components/icons";
import { SlaPanel } from "../../components/SlaPanel";
import { Timeline } from "../../components/Timeline";
import { useToast } from "../../components/Toasts";
import { Card, ErrorMessage, Notice, Spinner } from "../../components/ui";
import { useLiveRefresh } from "../../hooks/LiveEvents";
import { useAsync } from "../../hooks/useAsync";
import { formatDateTime, IMPACT_OPTIONS, relativeTime, URGENCY_OPTIONS } from "../../lib/format";

type Refresh = (incident?: IncidentDetail) => void;

function useRunner(onDone: Refresh) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const run = async (label: string, action: () => Promise<IncidentDetail | unknown>) => {
    setBusy(true);
    try {
      const result = await action();
      toast.success(label);
      onDone(result && typeof result === "object" && "available_actions" in result ? (result as IncidentDetail) : undefined);
      return true;
    } catch (err) {
      toast.error(err);
      return false;
    } finally {
      setBusy(false);
    }
  };
  return { busy, run };
}

// ---------------------------------------------------------------- actions

function TextAction({ label, placeholder, minLength, submitLabel, initial = "", onSubmit, onCancel, busy }: {
  label: string;
  placeholder: string;
  minLength: number;
  submitLabel: string;
  initial?: string;
  onSubmit: (text: string) => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const [text, setText] = useState(initial);
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(text);
      }}
    >
      <label className="label">{label}</label>
      <textarea className="input min-h-24" required={minLength > 0} minLength={minLength} value={text} placeholder={placeholder}
                onChange={(e) => setText(e.target.value)} autoFocus />
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
        <button className="btn-primary btn-sm" disabled={busy || text.trim().length < minLength}>{submitLabel}</button>
      </div>
    </form>
  );
}

function RatingInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex gap-1" role="radiogroup" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" role="radio" aria-checked={value === n} aria-label={`${n} stars`}
                className={`rounded p-0.5 ${n <= value ? "text-warning-solid" : "text-line-strong"} hover:text-warning-solid`} onClick={() => onChange(n)}>
          <StarIcon size={22} filled={n <= value} />
        </button>
      ))}
    </div>
  );
}

function VerifyForm({ incident, mode, busy, onSubmit, onCancel }: {
  incident: IncidentDetail;
  mode: "verify" | "feedback";
  busy: boolean;
  onSubmit: (rating: number, comment: string) => void;
  onCancel: () => void;
}) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); onSubmit(rating, comment); }}>
      {mode === "verify" && (
        <p className="text-sm text-muted">
          Confirm that <strong>{incident.resolution_summary ?? "the fix"}</strong> solved your problem.
        </p>
      )}
      <div>
        <span className="label">How was the support?</span>
        <RatingInput value={rating} onChange={setRating} />
      </div>
      <textarea className="input" placeholder="Optional comment" value={comment} maxLength={2000} onChange={(e) => setComment(e.target.value)} />
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
        <button className="btn-primary btn-sm" disabled={busy}>{mode === "verify" ? "Confirm resolved" : "Send feedback"}</button>
      </div>
    </form>
  );
}

function AssignForm({ incident, busy, onAssign, onAuto, onCancel }: {
  incident: IncidentDetail;
  busy: boolean;
  onAssign: (technicianId: number) => void;
  onAuto: () => void;
  onCancel: () => void;
}) {
  const technicians = useAsync(() => lookupsApi.technicians(), []);
  const [choice, setChoice] = useState<number | "">("");
  return (
    <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); if (choice !== "") onAssign(choice); }}>
      <label className="label">Assign to technician</label>
      <select className="input" value={choice} onChange={(e) => setChoice(e.target.value ? Number(e.target.value) : "")}>
        <option value="">Choose…</option>
        {technicians.data?.filter((t) => t.id !== incident.technician?.id).map((t) => (
          <option key={t.id} value={t.id}>{t.name} ({t.code})</option>
        ))}
      </select>
      <p className="hint">See the recommendations panel for who fits best and why.</p>
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
        {incident.status === "CLASSIFIED" && (
          <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={onAuto}>Auto-assign (current strategy)</button>
        )}
        <button className="btn-primary btn-sm" disabled={busy || choice === ""}>Assign</button>
      </div>
    </form>
  );
}

const ACTION_LABEL: Partial<Record<IncidentAction, string>> = {
  acknowledge: "Acknowledge",
  start_work: "Start work",
  request_info: "Request more info",
  resolve: "Resolve",
  provide_info: "Answer the question",
  verify: "Confirm it's fixed",
  reopen: "Not fixed - reopen",
  assign: "Assign / reassign",
  close: "Close incident",
  feedback: "Give feedback",
  update: "Edit details",
};

const PRIMARY: IncidentAction[] = ["acknowledge", "start_work", "resolve", "provide_info", "verify", "close"];

function ActionsPanel({ incident, refresh, resolutionDraft }: { incident: IncidentDetail; refresh: Refresh; resolutionDraft: string }) {
  const [open, setOpen] = useState<IncidentAction | null>(null);
  const { busy, run } = useRunner((updated) => { setOpen(null); refresh(updated); });
  const id = incident.id;
  const actions = incident.available_actions.filter((a) => a !== "comment" && ACTION_LABEL[a]);
  if (actions.length === 0) return null;

  const immediate: Partial<Record<IncidentAction, () => void>> = {
    acknowledge: () => run("Incident acknowledged - response SLA met", () => incidentsApi.acknowledge(id)),
    start_work: () => run("Work started", () => incidentsApi.start(id)),
  };
  const cancel = () => setOpen(null);
  let form: ReactNode = null;
  switch (open) {
    case "request_info":
      form = <TextAction label="What do you need from the reporter?" placeholder="e.g. Which browser and at what time did it fail?"
                         minLength={3} submitLabel="Send question (pauses the SLA clock)" busy={busy} onCancel={cancel}
                         onSubmit={(t) => run("Question sent - SLA clock paused", () => incidentsApi.requestInfo(id, t))} />;
      break;
    case "provide_info":
      form = <TextAction label="Your answer" placeholder="Give the technician the details they asked for" minLength={3}
                         submitLabel="Send answer" busy={busy} onCancel={cancel}
                         onSubmit={(t) => run("Answer sent to the technician", () => incidentsApi.provideInfo(id, t))} />;
      break;
    case "resolve":
      form = <TextAction label="Resolution details" placeholder="What was wrong and what did you do to fix it?" minLength={10}
                         initial={resolutionDraft} submitLabel="Mark resolved" busy={busy} onCancel={cancel}
                         onSubmit={(t) => run("Incident resolved - reporter notified", () => incidentsApi.resolve(id, t))} />;
      break;
    case "reopen":
      form = <TextAction label="What is still wrong?" placeholder="Describe why the problem is not fixed" minLength={3}
                         submitLabel="Reopen" busy={busy} onCancel={cancel}
                         onSubmit={(t) => run("Incident reopened", () => incidentsApi.reopen(id, t))} />;
      break;
    case "close":
      form = <TextAction label="Closure notes (optional)" placeholder="Anything worth recording" minLength={0}
                         submitLabel="Close incident" busy={busy} onCancel={cancel}
                         onSubmit={(t) => run("Incident closed", () => incidentsApi.close(id, t || null))} />;
      break;
    case "verify":
      form = <VerifyForm incident={incident} mode="verify" busy={busy} onCancel={cancel}
                         onSubmit={(r, c) => run("Thanks! Incident verified", () => incidentsApi.verify(id, r, c))} />;
      break;
    case "feedback":
      form = <VerifyForm incident={incident} mode="feedback" busy={busy} onCancel={cancel}
                         onSubmit={(r, c) => run("Thanks for your feedback", () => incidentsApi.feedback(id, r, c))} />;
      break;
    case "assign":
      form = <AssignForm incident={incident} busy={busy} onCancel={cancel}
                         onAssign={(t) => run("Technician assigned", () => incidentsApi.assign(id, t))}
                         onAuto={() => run("Assigned automatically", () => incidentsApi.autoAssign(id))} />;
      break;
    case "update":
      form = <EditForm incident={incident} busy={busy} onCancel={cancel}
                       onSave={(patch) => run("Incident updated", () => incidentsApi.update(id, patch))} />;
      break;
  }

  return (
    <Card title="Actions">
      {form ?? (
        <div className="flex flex-wrap gap-2">
          {actions.map((a) => (
            <button key={a} disabled={busy}
                    className={PRIMARY.includes(a) ? "btn-primary" : a === "reopen" ? "btn-danger" : "btn-secondary"}
                    onClick={() => (immediate[a] ? immediate[a]!() : setOpen(a))}>
              {ACTION_LABEL[a]}
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}

function EditForm({ incident, busy, onSave, onCancel }: {
  incident: IncidentDetail;
  busy: boolean;
  onSave: (patch: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const [impact, setImpact] = useState(incident.impact);
  const [urgency, setUrgency] = useState(incident.urgency);
  const [affected, setAffected] = useState(incident.affected_users);
  const [description, setDescription] = useState(incident.description);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSave({ impact, urgency, affected_users: affected, description });
  };
  return (
    <form className="space-y-3" onSubmit={submit}>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm">
          <span className="label">Impact</span>
          <select className="input" value={impact} onChange={(e) => setImpact(Number(e.target.value))}>
            {IMPACT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.value} · {o.label}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="label">Urgency</span>
          <select className="input" value={urgency} onChange={(e) => setUrgency(Number(e.target.value))}>
            {URGENCY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.value} · {o.label}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="label">Affected users</span>
          <input type="number" min={1} className="input" value={affected} onChange={(e) => setAffected(Math.max(1, Number(e.target.value) || 1))} />
        </label>
      </div>
      <label className="block text-sm">
        <span className="label">Description</span>
        <textarea className="input min-h-24" minLength={10} value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <p className="hint">Changing impact, urgency or affected users recalculates the priority and SLA deadlines.</p>
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
        <button className="btn-primary btn-sm" disabled={busy}>Save changes</button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------- conversation

const KIND_STYLE: Record<Comment["kind"], { label: string; className: string }> = {
  COMMENT: { label: "Comment", className: "border-l-line-strong" },
  NOTE: { label: "Investigation note", className: "border-l-line-strong" },
  INFO_REQUEST: { label: "Information requested", className: "border-l-warning-solid" },
  INFO_REPLY: { label: "Reply from reporter", className: "border-l-brand" },
  RESOLUTION: { label: "Resolution", className: "border-l-ok-solid" },
};

function Conversation({ incident, user, refresh }: { incident: IncidentDetail; user: User; refresh: Refresh }) {
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);
  const { busy, run } = useRunner(() => { setBody(""); refresh(); });
  const canComment = incident.available_actions.includes("comment");

  return (
    <Card title={`Conversation & notes (${incident.comments.length})`}>
      <ul className="space-y-3">
        {incident.comments.length === 0 && <li className="text-sm text-muted">No messages yet.</li>}
        {incident.comments.map((c) => {
          const style = c.is_internal
            ? { label: "Internal note, staff only", className: "border-l-faint bg-sunken" }
            : KIND_STYLE[c.kind];
          return (
            <li key={c.id ?? c.created_at} className={`rounded-r border border-line border-l-[3px] px-4 py-2.5 ${style.className}`}>
              <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2 text-xs text-muted">
                <span>
                  <span className="font-medium text-fg">{c.author?.name ?? "System"}</span> · {style.label}
                </span>
                <time className="tabular-nums" dateTime={c.created_at} title={formatDateTime(c.created_at)}>{relativeTime(c.created_at)}</time>
              </div>
              <p className="text-sm whitespace-pre-wrap text-fg">{c.body}</p>
            </li>
          );
        })}
      </ul>
      {canComment && (
        <form className="mt-4 space-y-2" onSubmit={(e) => {
          e.preventDefault();
          run(internal ? "Internal note added" : "Comment added", () => incidentsApi.comment(incident.id, body, internal));
        }}>
          <textarea className="input min-h-20" value={body} minLength={2} maxLength={5000} required onChange={(e) => setBody(e.target.value)}
                    placeholder={isStaff(user) ? "Add an investigation note or an update for the reporter" : "Add more information for the support team"} />
          <div className="flex items-center justify-between">
            {isStaff(user) ? (
              <label className="flex items-center gap-2 text-sm text-muted">
                <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} />
                Internal note (hidden from the reporter)
              </label>
            ) : <span />}
            <button className="btn-secondary btn-sm" disabled={busy || body.trim().length < 2}>Post</button>
          </div>
        </form>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- staff intelligence

function Recommendations({ incident, user, refresh }: { incident: IncidentDetail; user: User; refresh: Refresh }) {
  const recs = useAsync(() => incidentsApi.recommendations(incident.id), [incident.id, incident.technician?.id]);
  const { busy, run } = useRunner(refresh);
  const canAssign = incident.available_actions.includes("assign") && user.role === "ADMINISTRATOR";
  return (
    <Card title="Recommended technicians" flush>
      {recs.loading && !recs.data && <div className="px-4"><Spinner /></div>}
      {recs.data?.length === 0 && <p className="p-4 text-sm text-muted">No other technicians.</p>}
      <ol className="divide-y divide-line">
        {recs.data?.map((r, index) => (
          <li key={r.technician_id} className={`px-4 py-2.5 ${r.eligible ? "" : "opacity-55"}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-fg"><span className="mr-2 font-mono text-[11.5px] text-faint">{index + 1}</span>{r.name}{!r.eligible && <span className="ml-2 text-[12px] font-normal text-muted">not eligible</span>}</span>
              <span className="font-mono text-[12px] font-medium text-brand tabular-nums" title="Recommendation score">{r.score}</span>
            </div>
            <p className="mt-1 text-xs text-muted">{r.reasons.join(" · ")}</p>
            {canAssign && r.eligible && (
              <button className="btn-secondary btn-sm mt-2" disabled={busy}
                      onClick={() => run(`Assigned to ${r.name}`, () => incidentsApi.assign(incident.id, r.technician_id))}>
                Assign
              </button>
            )}
          </li>
        ))}
      </ol>
    </Card>
  );
}

function SuggestedFixes({ incident, onUse }: { incident: IncidentDetail; onUse: (text: string) => void }) {
  const fixes = useAsync(() => incidentsApi.suggestedResolutions(incident.id), [incident.id]);
  if (!fixes.data || fixes.data.length === 0) return null;
  const canResolve = incident.available_actions.includes("resolve");
  return (
    <Card title="Fixes that worked before">
      <ul className="space-y-3">
        {fixes.data.map((f) => (
          <li key={f.incident_id} className="text-sm">
            <div className="flex justify-between gap-2 text-xs text-muted">
              <Link className="link mono" to={`/incidents/${f.incident_id}`}>{f.number}</Link>
              <span>{Math.round(f.similarity * 100)}% similar</span>
            </div>
            <p className="text-muted">{f.title}</p>
            <p className="mt-1.5 border-l-2 border-ok-solid pl-3 text-fg">{f.resolution}</p>
            {canResolve && <button className="link mt-1 text-xs" onClick={() => onUse(f.resolution)}>Use as my resolution</button>}
          </li>
        ))}
      </ul>
    </Card>
  );
}

// ---------------------------------------------------------------- page

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[12px] text-muted">{label}</dt>
      <dd className="mt-0.5 text-[13.5px] text-fg">{children}</dd>
    </div>
  );
}

export function IncidentDetailPage() {
  const user = useUser();
  const id = Number(useParams().id);
  const incident = useAsync(() => incidentsApi.get(id), [id]);
  const audit = useAsync(() => incidentsApi.audit(id), [id]);
  const [resolutionDraft, setResolutionDraft] = useState("");
  const toast = useToast();

  const refresh: Refresh = (updated) => {
    if (updated) incident.setData(updated);
    else incident.reload();
    audit.reload();
  };
  useLiveRefresh(() => refresh(), id);

  if (incident.error) return <ErrorMessage error={incident.error} onRetry={incident.reload} />;
  if (!incident.data) return <Spinner />;
  const i = incident.data;
  const staff = isStaff(user);

  return (
    <div className="space-y-6">
      <div>
        <Link to={staff ? "/incidents" : "/employee"} className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-fg">
          <ArrowLeftIcon size={14} />
          {staff ? "Incidents" : "My incidents"}
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="font-mono text-[13px] text-muted">{i.number}</span>
          <PriorityBadge priority={i.priority} long />
          <StatusBadge status={i.status} />
          <EscalationBadge level={i.escalation_level} />
        </div>
        <h1 className="mt-1.5 max-w-4xl text-[24px]">{i.title}</h1>
        <p className="mt-1 text-[13px] text-muted">
          Reported by <span className="text-fg">{i.reporter?.name}</span> {relativeTime(i.created_at)} · {i.service?.name}
          {i.technician && <> · assigned to <span className="text-fg">{i.technician.name}</span></>}
        </p>
      </div>

      {i.status === "PENDING_INFO" && i.available_actions.includes("provide_info") && (
        <Notice tone="warning" title="The technician needs more information from you">
          Answer below to continue. The SLA clock is paused meanwhile.
        </Notice>
      )}
      {i.status === "RESOLVED" && i.available_actions.includes("verify") && (
        <Notice tone="ok" title="This incident was resolved">
          <strong className="font-medium">{i.resolution_summary}</strong>. Please confirm it is fixed, or reopen it.
        </Notice>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-6">
          <ActionsPanel incident={i} refresh={refresh} resolutionDraft={resolutionDraft} />
          {/* on small screens the SLA clocks come before the long history; on desktop they sit in the side rail */}
          {i.sla && <Card className="lg:hidden"><SlaPanel sla={i.sla} /></Card>}
          <Card title="Description">
            <p className="text-sm whitespace-pre-wrap text-fg">{i.description}</p>
            {i.resolution_summary && (
              <div className="mt-4 border-l-2 border-ok-solid pl-3 text-sm">
                <span className="font-medium text-ok">Resolution. </span>{i.resolution_summary}
              </div>
            )}
            {i.closure_notes && <p className="mt-2 text-sm text-muted"><strong>Closure notes:</strong> {i.closure_notes}</p>}
            {i.feedback && (
              <p className="mt-2 text-sm text-muted">
                Reporter feedback: <Stars rating={i.feedback.rating} /> {i.feedback.comment}
              </p>
            )}
          </Card>
          <Conversation incident={i} user={user} refresh={refresh} />
          <Card title="History (audit trail)">
            {audit.data ? <Timeline records={audit.data} /> : <Spinner />}
          </Card>
        </div>

        <aside className="min-w-0 space-y-4">
          {i.sla && <Card className="hidden lg:block"><SlaPanel sla={i.sla} /></Card>}
          <Card title="Details">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
              <Detail label="Category">
                {i.category?.name ?? "—"}
                {i.suggested_category && i.suggested_category.id !== i.category?.id && (
                  <span className="block text-xs text-muted">suggested: {i.suggested_category.name}</span>
                )}
              </Detail>
              <Detail label="Service">{i.service?.name}</Detail>
              <Detail label="Technician">{i.technician?.name ?? <span className="text-warning">Unassigned</span>}</Detail>
              <Detail label="Priority score">{i.priority_score ?? "—"} / 64</Detail>
              <Detail label="Impact">{IMPACT_OPTIONS[i.impact - 1]?.label} ({i.impact})</Detail>
              <Detail label="Urgency">{URGENCY_OPTIONS[i.urgency - 1]?.label} ({i.urgency})</Detail>
              <Detail label="Affected users">{i.affected_users}</Detail>
              <Detail label="Last update">{relativeTime(i.updated_at)}</Detail>
            </dl>
          </Card>
          {(i.links.length > 0 || i.parent_incident) && (
            <Card title="Related incidents">
              {i.parent_incident && (
                <p className="mb-3 text-sm">
                  Duplicate of <Link className="link" to={`/incidents/${i.parent_incident.id}`}>{i.parent_incident.code}</Link>{" "}
                  {i.parent_incident.name}
                </p>
              )}
              <ul className="space-y-2">
                {i.links.map((l) => (
                  <li key={l.incident_id} className="text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <Link className="link mono" to={`/incidents/${l.incident_id}`}>{l.number}</Link>
                      <span className="text-xs text-muted">
                        {l.link_type === "DUPLICATE" ? "duplicate" : "related"} · {Math.round(l.similarity * 100)}%
                      </span>
                    </div>
                    <p className="text-fg">{l.title}</p>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {staff && (
            <div className="flex items-baseline justify-between border-b border-line pt-2 pb-1.5">
              <h3>Assist</h3>
              <span className="text-[12px] text-faint">from incident history</span>
            </div>
          )}
          {staff && <Recommendations incident={i} user={user} refresh={refresh} />}
          {staff && (
            <SuggestedFixes incident={i} onUse={(text) => {
              setResolutionDraft(text);
              toast.info("Copied into the resolution form - click Resolve to review and submit.");
            }} />
          )}
        </aside>
      </div>
    </div>
  );
}
