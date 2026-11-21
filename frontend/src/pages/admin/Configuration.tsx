import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { adminApi } from "../../api/endpoints";
import { ALL_PRIORITIES, type Category, type Priority, type Service, type SLAPolicy } from "../../api/types";
import { useToast } from "../../components/Toasts";
import { Card, ErrorMessage, PageHeader, Spinner, Tabs } from "../../components/ui";
import { useAsync } from "../../hooks/useAsync";
import { formatMinutes } from "../../lib/format";

type Tab = "assignment" | "services" | "categories" | "sla";

/** Wraps an admin call with a toast and a reload. */
function useSave(reload: () => void) {
  const toast = useToast();
  return async (message: string, action: () => Promise<unknown>) => {
    try {
      await action();
      toast.success(message);
      reload();
      return true;
    } catch (err) {
      toast.error(err);
      return false;
    }
  };
}

// ---------------------------------------------------------------- assignment & escalation

function AssignmentTab() {
  const strategies = useAsync(() => adminApi.strategies(), []);
  const escalation = useAsync(() => adminApi.escalation(), []);
  const save = useSave(() => { strategies.reload(); escalation.reload(); });
  if (!strategies.data || !escalation.data) return <Spinner />;
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card title="Technician assignment strategy" className="lg:col-span-2">
        <p className="mb-4 text-sm text-muted">Applied to every new incident from the moment you switch. Each strategy is a separate class (Strategy pattern).</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {strategies.data.map((s) => (
            <button key={s.key} aria-pressed={s.active}
                    onClick={() => !s.active && save(`Assignment strategy switched to ${s.name}`, () => adminApi.setStrategy(s.key))}
                    className={`rounded-md border p-4 text-left transition ${s.active ? "border-brand bg-brand-soft ring-1 ring-brand" : "border-line hover:border-line-strong"}`}>
              <div className="flex items-center justify-between">
                <span className="font-semibold text-fg">{s.name}</span>
                {s.active && <span className="text-xs font-semibold text-brand-strong">ACTIVE</span>}
              </div>
              <p className="mt-1 text-sm text-muted">{s.description}</p>
            </button>
          ))}
        </div>
      </Card>
      <Card title="Automatic escalation" className="h-fit">
        <p className="text-sm text-muted">Unacknowledged incidents climb Technician → Team Lead → System Admin → IT Manager, one level per response window after the response deadline.</p>
        <label className="mt-4 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={escalation.data.include_p2}
                 onChange={(e) => save(`P2 escalation ${e.target.checked ? "enabled" : "disabled"}`, () => adminApi.setEscalation(e.target.checked))} />
          Also escalate P2 incidents (P1 always escalates)
        </label>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- services

function ServiceRow({ service, all, save }: { service: Service; all: Service[]; save: ReturnType<typeof useSave> }) {
  const [editing, setEditing] = useState(false);
  const [deps, setDeps] = useState(service.depends_on);
  const [criticality, setCriticality] = useState(service.business_criticality);
  const names = new Map(all.map((s) => [s.id, s.name]));
  return (
    <tr className={service.is_active ? "" : "opacity-50"}>
      <td><div className="font-medium">{service.name}</div><div className="mono text-faint">{service.code}</div></td>
      <td>
        {editing ? (
          <select className="input w-20" value={criticality} onChange={(e) => setCriticality(Number(e.target.value))}>
            {[1, 2, 3, 4].map((n) => <option key={n}>{n}</option>)}
          </select>
        ) : service.business_criticality}
      </td>
      <td className="text-muted">{service.owner_team}</td>
      <td className="max-w-sm text-xs">
        {editing ? (
          <div className="flex flex-wrap gap-1">
            {all.filter((s) => s.id !== service.id).map((s) => {
              const on = deps.includes(s.id);
              return (
                <button key={s.id} type="button" onClick={() => setDeps(on ? deps.filter((d) => d !== s.id) : [...deps, s.id])}
                        className={`rounded-[3px] border px-1.5 py-0.5 font-mono text-[11px] transition-colors ${on ? "border-brand bg-brand-soft text-fg" : "border-line text-muted hover:border-line-strong hover:text-fg"}`}>
                  {s.code}
                </button>
              );
            })}
          </div>
        ) : service.depends_on.map((d) => names.get(d)).join(", ") || "—"}
      </td>
      <td className="space-x-1 text-right whitespace-nowrap">
        {editing ? (
          <>
            <button className="btn-primary btn-sm" onClick={async () => {
              const ok = await save(`${service.name} updated`, async () => {
                await adminApi.updateService(service.id, { business_criticality: criticality });
                await adminApi.setDependencies(service.id, deps);
              });
              if (ok) setEditing(false);
            }}>Save</button>
            <button className="btn-secondary btn-sm" onClick={() => { setEditing(false); setDeps(service.depends_on); }}>Cancel</button>
          </>
        ) : (
          <>
            <button className="btn-secondary btn-sm" onClick={() => setEditing(true)}>Edit</button>
            <button className="btn-ghost btn-sm" onClick={() => save(`${service.name} ${service.is_active ? "retired" : "re-activated"}`,
              () => adminApi.updateService(service.id, { is_active: !service.is_active }))}>
              {service.is_active ? "Retire" : "Activate"}
            </button>
          </>
        )}
      </td>
    </tr>
  );
}

function ServicesTab() {
  const services = useAsync(() => adminApi.services(), []);
  const save = useSave(services.reload);
  const [form, setForm] = useState({ code: "", name: "", business_criticality: 2, owner_team: "General", description: "" });
  if (!services.data) return <Spinner />;
  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (await save(`Service ${form.name} created`, () => adminApi.createService(form))) {
      setForm({ code: "", name: "", business_criticality: 2, owner_team: "General", description: "" });
    }
  };
  return (
    <div className="space-y-6">
      <Card title="IT services">
        <p className="mb-3 text-sm text-muted">Business criticality (1-4) feeds the priority formula. Dependencies drive the correlation view; cycles are rejected.</p>
        <table className="data-table">
          <thead><tr><th>Service</th><th>Criticality</th><th>Owner</th><th>Depends on</th><th /></tr></thead>
          <tbody>{services.data.map((s) => <ServiceRow key={s.id} service={s} all={services.data!} save={save} />)}</tbody>
        </table>
      </Card>
      <Card title="Add a service">
        <form className="grid gap-3 sm:grid-cols-5" onSubmit={create}>
          <input className="input" placeholder="Code (e.g. CRM)" required minLength={2} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          <input className="input sm:col-span-2" placeholder="Name" required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select className="input" aria-label="Business criticality" value={form.business_criticality} onChange={(e) => setForm({ ...form, business_criticality: Number(e.target.value) })}>
            {[1, 2, 3, 4].map((n) => <option key={n} value={n}>Criticality {n}</option>)}
          </select>
          <input className="input" placeholder="Owner team" value={form.owner_team} onChange={(e) => setForm({ ...form, owner_team: e.target.value })} />
          <input className="input sm:col-span-4" placeholder="Description (optional)" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <button className="btn-primary">Add service</button>
        </form>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- categories

function CategoryRow({ category, save }: { category: Category; save: ReturnType<typeof useSave> }) {
  const [keywords, setKeywords] = useState(category.keywords.join(", "));
  const changed = keywords !== category.keywords.join(", ");
  const parsed = () => keywords.split(",").map((k) => k.trim()).filter(Boolean);
  return (
    <tr className={category.is_active ? "" : "opacity-50"}>
      <td><div className="font-medium">{category.name}</div><div className="mono text-faint">{category.code}</div></td>
      <td><input className="input text-xs" aria-label={`${category.name} keywords`} value={keywords} onChange={(e) => setKeywords(e.target.value)} /></td>
      <td className="space-x-1 text-right whitespace-nowrap">
        <button className="btn-primary btn-sm" disabled={!changed}
                onClick={() => save(`${category.name} keywords saved`, () => adminApi.updateCategory(category.id, { keywords: parsed() }))}>Save</button>
        <button className="btn-ghost btn-sm" onClick={() => save(`${category.name} ${category.is_active ? "disabled" : "enabled"}`,
          () => adminApi.updateCategory(category.id, { is_active: !category.is_active }))}>
          {category.is_active ? "Disable" : "Enable"}
        </button>
      </td>
    </tr>
  );
}

function CategoriesTab() {
  const categories = useAsync(() => adminApi.categories(), []);
  const save = useSave(categories.reload);
  const [form, setForm] = useState({ code: "", name: "", keywords: "" });
  if (!categories.data) return <Spinner />;
  const create = async (e: FormEvent) => {
    e.preventDefault();
    const ok = await save(`Category ${form.name} created - suggestions use it immediately`, () => adminApi.createCategory({
      code: form.code, name: form.name, keywords: form.keywords.split(",").map((k) => k.trim()).filter(Boolean),
    }));
    if (ok) setForm({ code: "", name: "", keywords: "" });
  };
  return (
    <div className="space-y-6">
      <Card title="Incident categories">
        <p className="mb-3 text-sm text-muted">Keywords power automatic category suggestion. Adding a category needs no code change (Open/Closed).</p>
        <table className="data-table">
          <thead><tr><th>Category</th><th>Keywords (comma separated)</th><th /></tr></thead>
          <tbody>{categories.data.map((c) => <CategoryRow key={`${c.id}-${c.keywords.join()}`} category={c} save={save} />)}</tbody>
        </table>
      </Card>
      <Card title="Add a category">
        <form className="grid gap-3 sm:grid-cols-4" onSubmit={create}>
          <input className="input" placeholder="Code (e.g. PRINTING)" required minLength={2} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          <input className="input" placeholder="Name" required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className="input" placeholder="Keywords: toner, print queue" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} />
          <button className="btn-primary">Add category</button>
        </form>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- SLA policies

function PolicyRow({ policy, serviceName, save }: { policy: SLAPolicy; serviceName: string; save: ReturnType<typeof useSave> }) {
  const [draft, setDraft] = useState({ response_minutes: policy.response_minutes, resolution_minutes: policy.resolution_minutes,
                                       warning_threshold_pct: policy.warning_threshold_pct });
  const changed = JSON.stringify(draft) !== JSON.stringify({ response_minutes: policy.response_minutes,
    resolution_minutes: policy.resolution_minutes, warning_threshold_pct: policy.warning_threshold_pct });
  const num = (key: keyof typeof draft) => (
    <input type="number" min={1} className="input w-24" aria-label={key} value={draft[key]}
           onChange={(e) => setDraft({ ...draft, [key]: Number(e.target.value) })} />
  );
  return (
    <tr>
      <td className="font-semibold">{policy.priority}</td>
      <td>{serviceName}</td>
      <td>{num("response_minutes")}<div className="text-xs text-faint">{formatMinutes(draft.response_minutes)}</div></td>
      <td>{num("resolution_minutes")}<div className="text-xs text-faint">{formatMinutes(draft.resolution_minutes)}</div></td>
      <td>{num("warning_threshold_pct")}</td>
      <td className="space-x-1 text-right whitespace-nowrap">
        <button className="btn-primary btn-sm" disabled={!changed}
                onClick={() => save(`${policy.priority} policy updated`, () => adminApi.updatePolicy(policy.id, draft))}>Save</button>
        {policy.service_id !== null && (
          <button className="btn-ghost btn-sm text-critical" onClick={() => save("Override deleted", () => adminApi.deletePolicy(policy.id))}>Delete</button>
        )}
      </td>
    </tr>
  );
}

function SlaTab() {
  const data = useAsync(() => Promise.all([adminApi.policies(), adminApi.services()]), []);
  const save = useSave(data.reload);
  const [form, setForm] = useState({ priority: "P1" as Priority, service_id: "", response_minutes: 5, resolution_minutes: 30, warning_threshold_pct: 75 });
  if (data.error) return <ErrorMessage error={data.error} onRetry={data.reload} />;
  if (!data.data) return <Spinner />;
  const [policies, services] = data.data;
  const names = new Map(services.map((s) => [s.id, s.name]));
  const sorted = [...policies].sort((a, b) => a.priority.localeCompare(b.priority) || (a.service_id ?? 0) - (b.service_id ?? 0));
  const create = (e: FormEvent) => {
    e.preventDefault();
    save("Service-specific SLA created", () => adminApi.createPolicy({ ...form, service_id: Number(form.service_id) }));
  };
  return (
    <div className="space-y-6">
      <Card title="SLA policies">
        <p className="mb-3 text-sm text-muted">Default policies apply to every service; a service-specific policy overrides the default for that priority. Changes affect new incidents (existing deadlines are kept).</p>
        <table className="data-table">
          <thead><tr><th>Priority</th><th>Applies to</th><th>Response (min)</th><th>Resolution (min)</th><th>Warn at %</th><th /></tr></thead>
          <tbody>
            {sorted.map((p) => (
              <PolicyRow key={`${p.id}-${p.response_minutes}-${p.resolution_minutes}-${p.warning_threshold_pct}`} policy={p}
                         serviceName={p.service_id === null ? "All services (default)" : names.get(p.service_id) ?? "?"} save={save} />
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Add a service-specific override">
        <form className="grid gap-3 sm:grid-cols-6" onSubmit={create}>
          <select className="input" aria-label="Priority" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as Priority })}>
            {ALL_PRIORITIES.map((p) => <option key={p}>{p}</option>)}
          </select>
          <select className="input sm:col-span-2" aria-label="Service" required value={form.service_id} onChange={(e) => setForm({ ...form, service_id: e.target.value })}>
            <option value="">Service…</option>
            {services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <input type="number" min={1} className="input" aria-label="Response minutes" value={form.response_minutes} onChange={(e) => setForm({ ...form, response_minutes: Number(e.target.value) })} />
          <input type="number" min={1} className="input" aria-label="Resolution minutes" value={form.resolution_minutes} onChange={(e) => setForm({ ...form, resolution_minutes: Number(e.target.value) })} />
          <button className="btn-primary">Add override</button>
        </form>
      </Card>
    </div>
  );
}

export function ConfigurationPage() {
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) ?? "assignment";
  return (
    <>
      <PageHeader title="Configuration" subtitle="Everything here takes effect immediately and is recorded in the audit log." />
      <Tabs<Tab>
        tabs={[
          { key: "assignment", label: "Assignment & escalation" },
          { key: "services", label: "IT services" },
          { key: "categories", label: "Categories" },
          { key: "sla", label: "SLA policies" },
        ]}
        active={tab}
        onChange={(t) => setParams({ tab: t })}
      />
      {tab === "assignment" && <AssignmentTab />}
      {tab === "services" && <ServicesTab />}
      {tab === "categories" && <CategoriesTab />}
      {tab === "sla" && <SlaTab />}
    </>
  );
}
