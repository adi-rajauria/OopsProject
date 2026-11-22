import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { incidentsApi, lookupsApi } from "../../api/endpoints";
import { ALL_PRIORITIES, ALL_SLA_STATUSES, ALL_STATUSES, type SortOrder } from "../../api/types";
import { isStaff, useUser } from "../../auth/AuthContext";
import { DownloadButton } from "../../components/DownloadButton";
import { IncidentTable } from "../../components/IncidentTable";
import { Card, ErrorMessage, PageHeader, Pagination, Spinner } from "../../components/ui";
import { useLiveRefresh } from "../../hooks/LiveEvents";
import { useAsync } from "../../hooks/useAsync";
import { PRIORITY_LABEL, SLA_LABEL, STATUS_LABEL } from "../../lib/format";

const MULTI = ["status", "priority", "sla_status", "service_id", "category_id"] as const;
const SINGLE = ["number", "q", "technician_id", "created_from", "created_to", "sort", "unassigned", "open_only"] as const;

function MultiSelect({ label, name, options, values, onChange }: {
  label: string;
  name: string;
  options: { value: string; label: string }[];
  values: string[];
  onChange: (values: string[]) => void;
}) {
  return (
    <fieldset>
      <legend className="label">{label}</legend>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => {
          const on = values.includes(o.value);
          return (
            <button type="button" key={o.value} aria-pressed={on} name={name}
                    onClick={() => onChange(on ? values.filter((v) => v !== o.value) : [...values, o.value])}
                    className={`rounded-[3px] border px-2 py-0.5 text-[12px] transition-colors ${on ? "border-brand bg-brand-soft text-fg" : "border-line bg-surface text-muted hover:border-line-strong hover:text-fg"}`}>
              {o.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

/** The URL keeps plain dates (YYYY-MM-DD); the API gets the user's local day boundaries in UTC. */
function localDayBoundary(day: string | null, edge: "start" | "end"): string | null {
  if (!day) return null;
  return new Date(`${day}T${edge === "start" ? "00:00:00" : "23:59:59.999"}`).toISOString();
}

/** Search & filter by 11 criteria. Filters live in the URL so a search can be bookmarked or shared. */
export function IncidentSearchPage() {
  const user = useUser();
  const staff = isStaff(user);
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? 1);
  const lookups = useAsync(
    () => Promise.all([lookupsApi.services(), lookupsApi.categories(), staff ? lookupsApi.technicians() : Promise.resolve([])]),
    [staff],
  );

  const query = Object.fromEntries([
    ...MULTI.map((k) => [k, params.getAll(k)]),
    ...SINGLE.map((k) => [k, params.get(k)]),
    ["created_from", localDayBoundary(params.get("created_from"), "start")],
    ["created_to", localDayBoundary(params.get("created_to"), "end")],
    ["page", page],
    ["page_size", 20],
  ]);
  const result = useAsync(() => incidentsApi.search(query), [params.toString()]);
  useLiveRefresh(() => result.reload());

  const [draft, setDraft] = useState({ number: params.get("number") ?? "", q: params.get("q") ?? "" });
  const update = (changes: Record<string, string | string[] | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      next.delete(key);
      if (Array.isArray(value)) value.forEach((v) => next.append(key, v));
      else if (value) next.set(key, value);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next);
  };
  const submitText = (e: FormEvent) => {
    e.preventDefault();
    update({ number: draft.number.trim() || null, q: draft.q.trim() || null });
  };
  const [services, categories, technicians] = lookups.data ?? [[], [], []];
  const activeFilters = [...params.keys()].filter((k) => k !== "page" && k !== "sort").length;

  return (
    <>
      <PageHeader title={staff ? "Incidents" : "Search my incidents"}
                  subtitle="Combine any filters; results update live as incidents change." />
      <div className="grid items-start gap-6 lg:grid-cols-[264px_minmax(0,1fr)]">
        <Card title="Filters"
              actions={activeFilters > 0 && (
                <button className="link text-xs" onClick={() => { setDraft({ number: "", q: "" }); setParams(new URLSearchParams()); }}>
                  Clear all
                </button>
              )}>
          <form className="space-y-4" onSubmit={submitText}>
            <div>
              <label className="label" htmlFor="number">Incident ID</label>
              <input id="number" className="input" placeholder="DCN-1001" value={draft.number}
                     onChange={(e) => setDraft({ ...draft, number: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="q">Text</label>
              <input id="q" className="input" placeholder="words in title or description" value={draft.q}
                     onChange={(e) => setDraft({ ...draft, q: e.target.value })} />
            </div>
            <button className="btn-secondary btn-sm w-full">Apply text filters</button>
          </form>
          <div className="mt-5 space-y-4">
            <MultiSelect label="Status" name="status" values={params.getAll("status")} onChange={(v) => update({ status: v })}
                         options={ALL_STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }))} />
            <MultiSelect label="Priority" name="priority" values={params.getAll("priority")} onChange={(v) => update({ priority: v })}
                         options={ALL_PRIORITIES.map((p) => ({ value: p, label: PRIORITY_LABEL[p] }))} />
            <MultiSelect label="SLA status" name="sla_status" values={params.getAll("sla_status")} onChange={(v) => update({ sla_status: v })}
                         options={ALL_SLA_STATUSES.map((s) => ({ value: s, label: SLA_LABEL[s] }))} />
            <div>
              <label className="label" htmlFor="service">Service</label>
              <select id="service" className="input" value={params.get("service_id") ?? ""}
                      onChange={(e) => update({ service_id: e.target.value ? [e.target.value] : [] })}>
                <option value="">Any service</option>
                {services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="category">Category</label>
              <select id="category" className="input" value={params.get("category_id") ?? ""}
                      onChange={(e) => update({ category_id: e.target.value ? [e.target.value] : [] })}>
                <option value="">Any category</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            {staff && (
              <div>
                <label className="label" htmlFor="tech">Technician</label>
                <select id="tech" className="input" value={params.get("technician_id") ?? ""}
                        onChange={(e) => update({ technician_id: e.target.value || null })}>
                  <option value="">Anyone</option>
                  {technicians.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
                <label className="mt-2 flex items-center gap-2 text-sm text-muted">
                  <input type="checkbox" checked={params.get("unassigned") === "true"}
                         onChange={(e) => update({ unassigned: e.target.checked ? "true" : null })} />
                  Unassigned only
                </label>
              </div>
            )}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="label" htmlFor="from">From</label>
                <input id="from" type="date" className="input" value={params.get("created_from") ?? ""}
                       onChange={(e) => update({ created_from: e.target.value || null })} />
              </div>
              <div>
                <label className="label" htmlFor="to">To</label>
                <input id="to" type="date" className="input" value={params.get("created_to") ?? ""}
                       onChange={(e) => update({ created_to: e.target.value || null })} />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-muted">
              <input type="checkbox" checked={params.get("open_only") === "true"}
                     onChange={(e) => update({ open_only: e.target.checked ? "true" : null })} />
              Open incidents only
            </label>
          </div>
        </Card>

        <Card flush
              title={result.data ? `${result.data.total} result${result.data.total === 1 ? "" : "s"}` : "Results"}
              actions={
                <div className="flex items-center gap-2">
                  {/* Exports every matching incident (all pages) with the same filters and visibility. */}
                  {(result.data?.total ?? 0) > 0 && (
                    <DownloadButton onDownload={() => incidentsApi.exportCsv({ ...query, page: undefined, page_size: undefined })} />
                  )}
                  <select className="input h-7 w-auto py-0 text-[13px]" aria-label="Sort" value={params.get("sort") ?? "-created_at"}
                          onChange={(e) => update({ sort: e.target.value as SortOrder })}>
                    <option value="-created_at">Newest first</option>
                    <option value="created_at">Oldest first</option>
                    <option value="priority">Priority</option>
                    <option value="-updated_at">Recently updated</option>
                  </select>
                </div>
              }>
          {result.error && <div className="p-4"><ErrorMessage error={result.error} onRetry={result.reload} /></div>}
          {result.loading && !result.data && <div className="px-4"><Spinner /></div>}
          {result.data && (
            <>
              <IncidentTable incidents={result.data.items}
                             columns={staff ? ["service", "reporter", "technician", "due"] : ["service", "technician"]} />
              {result.data.total > 0 && (
                <Pagination page={result.data.page} pages={result.data.pages} total={result.data.total}
                            onPage={(p) => update({ page: String(p) })} />
              )}
            </>
          )}
        </Card>
      </div>
    </>
  );
}
