import { useState, type FormEvent } from "react";
import { adminApi, lookupsApi } from "../../api/endpoints";
import type { AdminLevel, Category, Role, User } from "../../api/types";
import { useUser } from "../../auth/AuthContext";
import { RoleBadge } from "../../components/badges";
import { useToast } from "../../components/Toasts";
import { Card, ErrorMessage, PageHeader, Spinner } from "../../components/ui";
import { useAsync } from "../../hooks/useAsync";
import { formatDateTime } from "../../lib/format";

function SkillPicker({ categories, value, onChange }: { categories: Category[]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {categories.map((c) => {
        const on = value.includes(c.code);
        return (
          <button type="button" key={c.code} aria-pressed={on}
                  onClick={() => onChange(on ? value.filter((v) => v !== c.code) : [...value, c.code])}
                  className={`rounded-full border px-2.5 py-0.5 text-xs ${on ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]" : "border-slate-200 text-slate-600"}`}>
            {c.name}
          </button>
        );
      })}
    </div>
  );
}

const EMPTY_USER = {
  role: "TECHNICIAN" as Role, full_name: "", email: "", password: "", phone: "", department: "",
  admin_level: "SYSTEM_ADMIN" as AdminLevel, skills: [] as string[], experience_years: 1, max_workload: 8,
  team: "General", is_team_lead: false,
};

function CreateUserForm({ categories, onCreated }: { categories: Category[]; onCreated: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY_USER);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const user = await adminApi.createUser({
        role: form.role, email: form.email, full_name: form.full_name, password: form.password,
        phone: form.phone || null, department: form.department || null,
        admin_level: form.role === "ADMINISTRATOR" ? form.admin_level : null,
        technician: form.role === "TECHNICIAN"
          ? { skills: form.skills, experience_years: form.experience_years, max_workload: form.max_workload,
              team: form.team, is_team_lead: form.is_team_lead }
          : null,
      });
      toast.success(`${user.full_name} (${user.code}) created`);
      setForm(EMPTY_USER);
      onCreated();
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="space-y-3" onSubmit={submit}>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm"><span className="label">Role</span>
          <select className="input" value={form.role} onChange={(e) => set("role", e.target.value as Role)}>
            <option value="EMPLOYEE">Employee</option>
            <option value="TECHNICIAN">Technician</option>
            <option value="ADMINISTRATOR">Administrator</option>
          </select>
        </label>
        <label className="text-sm"><span className="label">Full name</span>
          <input className="input" required minLength={2} value={form.full_name} onChange={(e) => set("full_name", e.target.value)} />
        </label>
        <label className="text-sm"><span className="label">Email</span>
          <input className="input" type="email" required value={form.email} onChange={(e) => set("email", e.target.value)} />
        </label>
        <label className="text-sm"><span className="label">Initial password</span>
          <input className="input" type="password" required minLength={8} value={form.password} onChange={(e) => set("password", e.target.value)} />
        </label>
        <label className="text-sm"><span className="label">Phone (SMS)</span>
          <input className="input" value={form.phone} onChange={(e) => set("phone", e.target.value)} />
        </label>
        <label className="text-sm"><span className="label">Department</span>
          <input className="input" value={form.department} onChange={(e) => set("department", e.target.value)} />
        </label>
      </div>
      {form.role === "ADMINISTRATOR" && (
        <label className="block max-w-xs text-sm"><span className="label">Administrator level</span>
          <select className="input" value={form.admin_level} onChange={(e) => set("admin_level", e.target.value as AdminLevel)}>
            <option value="SYSTEM_ADMIN">System administrator</option>
            <option value="IT_MANAGER">IT manager</option>
          </select>
        </label>
      )}
      {form.role === "TECHNICIAN" && (
        <div className="space-y-3 rounded-lg bg-slate-50 p-3">
          <div><span className="label">Skills (incident categories)</span>
            <SkillPicker categories={categories} value={form.skills} onChange={(v) => set("skills", v)} />
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            <label className="text-sm"><span className="label">Experience (years)</span>
              <input className="input" type="number" min={0} max={60} value={form.experience_years} onChange={(e) => set("experience_years", Number(e.target.value))} />
            </label>
            <label className="text-sm"><span className="label">Max workload</span>
              <input className="input" type="number" min={1} max={50} value={form.max_workload} onChange={(e) => set("max_workload", Number(e.target.value))} />
            </label>
            <label className="text-sm"><span className="label">Team</span>
              <input className="input" value={form.team} onChange={(e) => set("team", e.target.value)} />
            </label>
            <label className="mt-6 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_team_lead} onChange={(e) => set("is_team_lead", e.target.checked)} /> Team lead
            </label>
          </div>
        </div>
      )}
      <div className="flex justify-end"><button className="btn-primary" disabled={busy}>Create user</button></div>
    </form>
  );
}

function TechnicianEditor({ user, categories, onSaved, onCancel }: { user: User; categories: Category[]; onSaved: () => void; onCancel: () => void }) {
  const toast = useToast();
  const p = user.technician_profile!;
  const [draft, setDraft] = useState({ ...p });
  const save = async () => {
    try {
      await adminApi.updateTechnician(user.id, draft);
      toast.success(`${user.full_name} updated`);
      onSaved();
    } catch (err) {
      toast.error(err);
    }
  };
  return (
    <div className="space-y-3 rounded-lg bg-slate-50 p-3">
      <SkillPicker categories={categories} value={draft.skills} onChange={(skills) => setDraft({ ...draft, skills })} />
      <div className="flex flex-wrap items-end gap-3 text-sm">
        <label><span className="label">Experience</span>
          <input className="input w-24" type="number" min={0} value={draft.experience_years} onChange={(e) => setDraft({ ...draft, experience_years: Number(e.target.value) })} />
        </label>
        <label><span className="label">Max workload</span>
          <input className="input w-24" type="number" min={1} value={draft.max_workload} onChange={(e) => setDraft({ ...draft, max_workload: Number(e.target.value) })} />
        </label>
        <label><span className="label">Team</span>
          <input className="input w-32" value={draft.team} onChange={(e) => setDraft({ ...draft, team: e.target.value })} />
        </label>
        <label className="flex items-center gap-1.5 pb-2"><input type="checkbox" checked={draft.is_team_lead} onChange={(e) => setDraft({ ...draft, is_team_lead: e.target.checked })} />Lead</label>
        <label className="flex items-center gap-1.5 pb-2"><input type="checkbox" checked={draft.is_available} onChange={(e) => setDraft({ ...draft, is_available: e.target.checked })} />Available</label>
        <button className="btn-primary btn-sm" onClick={save}>Save</button>
        <button className="btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

export function UsersPage() {
  const me = useUser();
  const toast = useToast();
  const [role, setRole] = useState<Role | "">("");
  const [editing, setEditing] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const users = useAsync(() => adminApi.users(role || undefined), [role]);
  const categories = useAsync(() => lookupsApi.categories(), []);

  const toggleActive = async (u: User) => {
    try {
      await adminApi.setActive(u.id, !u.is_active);
      toast.success(`${u.full_name} ${u.is_active ? "deactivated" : "activated"}`);
      users.reload();
    } catch (err) {
      toast.error(err);
    }
  };

  return (
    <>
      <PageHeader title="Users & technicians" subtitle="Self-registration creates employees; technicians and administrators are created here."
                  actions={<button className="btn-primary" onClick={() => setShowCreate((s) => !s)}>{showCreate ? "Close" : "+ New user"}</button>} />
      {showCreate && categories.data && (
        <Card title="New user" className="mb-6">
          <CreateUserForm categories={categories.data} onCreated={() => { setShowCreate(false); users.reload(); }} />
        </Card>
      )}
      <Card title={
        <select className="input w-auto" aria-label="Filter by role" value={role} onChange={(e) => setRole(e.target.value as Role | "")}>
          <option value="">All roles</option>
          <option value="EMPLOYEE">Employees</option>
          <option value="TECHNICIAN">Technicians</option>
          <option value="ADMINISTRATOR">Administrators</option>
        </select>
      }>
        {users.error && <ErrorMessage error={users.error} onRetry={users.reload} />}
        {!users.data ? <Spinner /> : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr><th>User</th><th>Role</th><th>Details</th><th>Joined</th><th>Status</th><th /></tr></thead>
              <tbody>
                {users.data.map((u) => (
                  <tr key={u.id} className={u.is_active ? "" : "opacity-50"}>
                    <td>
                      <div className="font-medium text-slate-800">{u.full_name} <span className="text-xs text-slate-400">{u.code}</span></div>
                      <div className="text-xs text-slate-500">{u.email}{u.phone ? ` · ${u.phone}` : ""}</div>
                    </td>
                    <td>
                      <RoleBadge role={u.role} />
                      {u.admin_level && <div className="mt-1 text-xs text-slate-500">{u.admin_level === "IT_MANAGER" ? "IT manager" : "System admin"}</div>}
                    </td>
                    <td className="max-w-md text-xs text-slate-600">
                      {u.technician_profile ? (
                        editing === u.id && categories.data ? (
                          <TechnicianEditor user={u} categories={categories.data} onCancel={() => setEditing(null)}
                                            onSaved={() => { setEditing(null); users.reload(); }} />
                        ) : (
                          <>
                            <div>{u.technician_profile.skills.join(", ") || "no skills"}</div>
                            <div>{u.technician_profile.team}{u.technician_profile.is_team_lead ? " · team lead" : ""} · {u.technician_profile.experience_years} yrs · max {u.technician_profile.max_workload} · {u.technician_profile.is_available ? "available" : "away"}</div>
                          </>
                        )
                      ) : (u.department ?? "—")}
                    </td>
                    <td className="text-xs whitespace-nowrap text-slate-500">{formatDateTime(u.created_at)}</td>
                    <td>{u.is_active ? <span className="text-emerald-700">Active</span> : <span className="text-slate-500">Deactivated</span>}</td>
                    <td className="space-x-1 text-right whitespace-nowrap">
                      {u.technician_profile && editing !== u.id && (
                        <button className="btn-secondary btn-sm" onClick={() => setEditing(u.id)}>Edit profile</button>
                      )}
                      {u.id !== me.id && (
                        <button className={u.is_active ? "btn-ghost btn-sm text-rose-600" : "btn-secondary btn-sm"} onClick={() => toggleActive(u)}>
                          {u.is_active ? "Deactivate" : "Activate"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
