import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { ApiError } from "../../api/client";
import { incidentsApi, intelligenceApi, lookupsApi } from "../../api/endpoints";
import type { CategorySuggestion, IncidentLink, SelfHelpTip, SeverityHint } from "../../api/types";
import { StatusBadge } from "../../components/badges";
import { errorMessage, useToast } from "../../components/Toasts";
import { Card, ErrorMessage, PageHeader, Spinner } from "../../components/ui";
import { appendSpoken, VoiceButton, VoiceStatus } from "../../components/VoiceInput";
import { useAsync, useDebounced } from "../../hooks/useAsync";
import { useSpeechRecognition } from "../../hooks/useSpeechRecognition";
import { IMPACT_OPTIONS, URGENCY_OPTIONS } from "../../lib/format";

/** A connected 1-4 scale: reads as one question with ordered answers, not four separate cards. */
function ScaleChooser({ name, value, onChange, options }: {
  name: string;
  value: number;
  onChange: (v: number) => void;
  options: { value: number; label: string; hint: string }[];
}) {
  return (
    <div className="grid grid-cols-2 overflow-hidden rounded border border-line-strong sm:grid-cols-4" role="radiogroup" aria-label={name}>
      {options.map((o, index) => (
        <button
          type="button"
          role="radio"
          aria-checked={value === o.value}
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`relative border-line px-3 py-2 text-left transition-colors ${index % 2 ? "border-l" : ""} ${
            index > 1 ? "border-t sm:border-t-0" : ""} ${index === 2 ? "sm:border-l" : ""} ${
            value === o.value ? "bg-brand-soft shadow-[inset_0_-2px_0_var(--c-brand)]" : "bg-surface hover:bg-sunken"
          }`}
        >
          <div className="flex items-baseline gap-1.5">
            <span className={`font-mono text-[11px] ${value === o.value ? "text-brand" : "text-faint"}`}>{o.value}</span>
            <span className="text-[13.5px] font-medium text-fg">{o.label}</span>
          </div>
          <div className="text-[12px] text-muted">{o.hint}</div>
        </button>
      ))}
    </div>
  );
}

/** "Your description suggests …" under a scale, only when it differs from the current choice. */
function ScaleHint({ level, reason, current, options, onUse }: {
  level: number | null;
  reason: string | null;
  current: number;
  options: { value: number; label: string }[];
  onUse: (v: number) => void;
}) {
  if (level === null || level === current) return null;
  const label = options.find((o) => o.value === level)?.label ?? level;
  return (
    <p className="hint">
      Your description suggests <strong>{label}</strong> ({reason}){" "}
      <button type="button" className="link" onClick={() => onUse(level)}>Use it</button>
    </p>
  );
}

export function ReportIncidentPage() {
  const toast = useToast();
  const navigate = useNavigate();
  const lookups = useAsync(() => Promise.all([lookupsApi.services(), lookupsApi.categories()]), []);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [serviceId, setServiceId] = useState<number | "">("");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [impact, setImpact] = useState(2);
  const [urgency, setUrgency] = useState(2);
  const [affected, setAffected] = useState(1);
  const [suggestions, setSuggestions] = useState<CategorySuggestion[]>([]);
  const [similar, setSimilar] = useState<IncidentLink[]>([]);
  const [tips, setTips] = useState<SelfHelpTip[]>([]);
  const [severity, setSeverity] = useState<SeverityHint | null>(null);
  // Voice reporting: each spoken phrase is appended to the description; the first one also becomes the title.
  const addSpokenText = useCallback((spoken: string) => {
    if (!spoken) return;
    setTitle((current) => current || appendSpoken("", spoken, 200));
    setDescription((current) => appendSpoken(current, spoken));
  }, []);
  const voice = useSpeechRecognition(addSpokenText);
  const [blocking, setBlocking] = useState<IncidentLink[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  // Live intelligence while typing (debounced so we don't call the API on every keystroke).
  // Debounce a string (stable identity) so the effect only fires when the text really changed.
  const debouncedKey = useDebounced(JSON.stringify({ title, description, serviceId }), 600);
  useEffect(() => {
    const text = JSON.parse(debouncedKey) as { title: string; description: string; serviceId: number | "" };
    if (text.title.trim().length < 4) {
      setSuggestions([]);
      setSimilar([]);
      setTips([]);
      setSeverity(null);
      return;
    }
    intelligenceApi.suggestCategory(text.title, text.description).then(setSuggestions).catch(() => setSuggestions([]));
    intelligenceApi.suggestSeverity(text.title, text.description).then(setSeverity).catch(() => setSeverity(null));
    intelligenceApi.selfHelp(text.title, text.description).then(setTips).catch(() => setTips([]));
    if (text.serviceId !== "") {
      intelligenceApi.checkDuplicates(text.title, text.description, text.serviceId).then(setSimilar).catch(() => setSimilar([]));
    } else {
      setSimilar([]);
    }
  }, [debouncedKey]);

  if (lookups.error) return <ErrorMessage error={lookups.error} onRetry={lookups.reload} />;
  if (!lookups.data) return <Spinner />;
  const [services, categories] = lookups.data;
  const top = suggestions[0];

  const submit = async (e: FormEvent | null, force = false) => {
    e?.preventDefault();
    if (serviceId === "") {
      setError("Please choose the affected service");
      return;
    }
    setBusy(true);
    setError(undefined);
    try {
      const created = await incidentsApi.create({
        title, description, service_id: serviceId, impact, urgency, affected_users: affected,
        category_id: categoryId === "" ? null : categoryId, force,
      });
      toast.success(
        `${created.number} created · ${created.priority} · ${created.technician ? `assigned to ${created.technician.name}` : "waiting for assignment"}`,
      );
      navigate(`/incidents/${created.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.code === "DUPLICATE_INCIDENT") {
        setBlocking((err.details.matches as IncidentLink[]) ?? []);
      } else {
        setError(errorMessage(err));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Report an incident" subtitle="Describe what is wrong. We will classify, prioritise and route it automatically." />
      <div className="grid gap-6 lg:grid-cols-3">
        <form onSubmit={(e) => submit(e)} className="panel space-y-5 p-5 lg:col-span-2">
          <div>
            <label className="label" htmlFor="title">Short summary</label>
            <input id="title" className="input" required minLength={5} maxLength={200} value={title}
                   placeholder="e.g. Payment application unavailable" onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <div className="flex items-end justify-between gap-2">
              <label className="label" htmlFor="desc">What happened?</label>
              <VoiceButton voice={voice} className="mb-1.5" />
            </div>
            <textarea id="desc" className="input min-h-32" required minLength={10} maxLength={5000} value={description}
                      placeholder="What were you doing, what did you expect, what error did you see?"
                      onChange={(e) => setDescription(e.target.value)} />
            <VoiceStatus voice={voice} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="service">Affected service</label>
              <select id="service" className="input" required value={serviceId}
                      onChange={(e) => setServiceId(e.target.value ? Number(e.target.value) : "")}>
                <option value="">Choose a service…</option>
                {services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="category">Category</label>
              <select id="category" className="input" value={categoryId}
                      onChange={(e) => setCategoryId(e.target.value ? Number(e.target.value) : "")}>
                <option value="">Let the system decide{top ? ` (${top.name})` : ""}</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              {top && categoryId !== top.category_id && (
                <p className="hint">
                  Suggested: <strong>{top.name}</strong> ({Math.round(top.confidence * 100)}% · {top.reason}){" "}
                  <button type="button" className="link" onClick={() => setCategoryId(top.category_id)}>Use it</button>
                </p>
              )}
            </div>
          </div>
          <div>
            <span className="label">Who is affected?</span>
            <ScaleChooser name="Impact" value={impact} onChange={setImpact} options={IMPACT_OPTIONS} />
            <ScaleHint level={severity?.impact ?? null} reason={severity?.impact_reason ?? null} current={impact}
                       options={IMPACT_OPTIONS} onUse={setImpact} />
          </div>
          <div>
            <span className="label">How urgent is it?</span>
            <ScaleChooser name="Urgency" value={urgency} onChange={setUrgency} options={URGENCY_OPTIONS} />
            <ScaleHint level={severity?.urgency ?? null} reason={severity?.urgency_reason ?? null} current={urgency}
                       options={URGENCY_OPTIONS} onUse={setUrgency} />
          </div>
          <div className="max-w-xs">
            <label className="label" htmlFor="affected">Roughly how many people are affected?</label>
            <input id="affected" type="number" min={1} max={100000} className="input" value={affected}
                   onChange={(e) => setAffected(Math.max(1, Number(e.target.value) || 1))} />
          </div>

          {blocking && (
            <div className="rounded-r border-l-[3px] border-l-warning-solid bg-warning-soft p-4 text-[13px] text-fg" role="alert">
              <p className="font-semibold">You reported something almost identical a few minutes ago:</p>
              <ul className="mt-2 space-y-1">
                {blocking.map((m) => (
                  <li key={m.incident_id}>
                    <Link className="link mono" to={`/incidents/${m.incident_id}`}>{m.number}</Link> {m.title}
                    {" "}<span className="text-muted">({Math.round(m.similarity * 100)}% similar)</span>
                  </li>
                ))}
              </ul>
              <div className="mt-3 flex gap-2">
                <button type="button" className="btn-secondary btn-sm" onClick={() => setBlocking(null)}>Edit my report</button>
                <button type="button" className="btn-primary btn-sm" disabled={busy} onClick={() => submit(null, true)}>
                  It is a different problem, submit anyway
                </button>
              </div>
            </div>
          )}
          {error && <ErrorMessage error={error} />}
          <div className="flex justify-end gap-2">
            <Link className="btn-secondary" to="/employee">Cancel</Link>
            <button className="btn-primary" disabled={busy}>{busy ? "Submitting…" : "Submit incident"}</button>
          </div>
        </form>

        <aside className="space-y-4">
          {tips.length > 0 && (
            <Card title="Try this first">
              <p className="mb-3 text-[12.5px] text-muted">These fixes solved similar problems before. If one works, you don't need to submit.</p>
              <ul className="space-y-3">
                {tips.map((t, index) => (
                  <li key={index} className="text-[13px]">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-muted">{t.title}</span>
                      <span className="shrink-0 font-mono text-[11.5px] text-muted">{Math.round(t.similarity * 100)}%</span>
                    </div>
                    <p className="mt-1 border-l-2 border-ok-solid pl-3 text-fg">{t.resolution}</p>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <Card title="Is it already reported?">
            {serviceId === "" || title.trim().length < 4 ? (
              <p className="text-[13px] text-muted">Choose a service and type a summary to check for similar open incidents.</p>
            ) : similar.length === 0 ? (
              <p className="text-[13px] text-muted">No similar open incidents on this service in the last 24 hours.</p>
            ) : (
              <ul className="space-y-3">
                {similar.map((m) => (
                  <li key={m.incident_id} className="text-[13px]">
                    <div className="flex items-center justify-between gap-2">
                      <Link className="link mono" to={`/incidents/${m.incident_id}`}>{m.number}</Link>
                      <span className="font-mono text-[11.5px] text-muted">{Math.round(m.similarity * 100)}%</span>
                    </div>
                    <p className="text-fg">{m.title}</p>
                    <StatusBadge status={m.status} />
                  </li>
                ))}
                <li className="border-t border-line pt-3 text-[12px] text-muted">
                  You can still submit: your report will be linked to these so the technician sees the full picture.
                </li>
              </ul>
            )}
          </Card>
          <Card title="What happens next">
            <ol className="space-y-2 text-[13px] text-muted [counter-reset:step] [&>li]:relative [&>li]:pl-6 [&>li]:[counter-increment:step] [&>li]:before:absolute [&>li]:before:left-0 [&>li]:before:font-mono [&>li]:before:text-[11.5px] [&>li]:before:text-faint [&>li]:before:content-[counter(step,decimal-leading-zero)]">
              <li>Priority is calculated from impact, urgency and how critical the service is.</li>
              <li>The matching SLA sets response and resolution deadlines.</li>
              <li>A suitable technician is assigned and notified.</li>
              <li>You get updates here, in the bell and by e-mail.</li>
            </ol>
          </Card>
        </aside>
      </div>
    </>
  );
}
