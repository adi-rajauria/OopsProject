import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { HOME_BY_ROLE, useAuth } from "../../auth/AuthContext";
import { errorMessage } from "../../components/Toasts";

const DEMO_ACCOUNTS = [
  { email: "riya@itsm.demo", label: "Employee", who: "Riya Kapoor · Finance" },
  { email: "kabir@itsm.demo", label: "Technician", who: "Kabir Rao · Infra team lead" },
  { email: "admin@itsm.demo", label: "Administrator", who: "Ada Sharma · System Admin" },
];
const DEMO_PASSWORD = "Demo@1234";

export function AuthShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-gradient-to-br from-indigo-700 via-indigo-600 to-violet-600 p-12 text-white lg:flex">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-white/15 font-bold">IT</span> I-ITSM
        </div>
        <div>
          <h1 className="text-4xl leading-tight font-semibold text-white">
            Report, prioritise and resolve IT incidents — before SLAs slip.
          </h1>
          <ul className="mt-8 space-y-3 text-indigo-100">
            <li>• Automatic priority, SLA and technician assignment</li>
            <li>• Duplicate detection and smart category suggestions</li>
            <li>• Live dashboards, escalations and a full audit trail</li>
          </ul>
        </div>
        <p className="text-sm text-indigo-200">CS F213 · Intelligent IT Service Management</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <h1 className="mb-6">{title}</h1>
          {children}
        </div>
      </div>
    </div>
  );
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={HOME_BY_ROLE[user.role]} replace />;

  const submit = async (e: FormEvent, override?: { email: string; password: string }) => {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      const signedIn = await login(override?.email ?? email, override?.password ?? password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from !== "/" ? from : HOME_BY_ROLE[signedIn.role], { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Sign in">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" className="input" type="email" autoComplete="username" required value={email}
                 onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <input id="password" className="input" type="password" autoComplete="current-password" required
                 value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <p className="mt-4 text-sm text-slate-600">
        New employee? <Link className="link" to="/register">Create an account</Link>
      </p>

      <div className="mt-8 rounded-xl border border-slate-200 bg-white p-4">
        <p className="mb-3 text-xs font-semibold tracking-wide text-slate-500 uppercase">Demo accounts</p>
        <div className="grid gap-2">
          {DEMO_ACCOUNTS.map((a) => (
            <button key={a.email} className="btn-secondary justify-between" disabled={busy}
                    onClick={(e) => submit(e, { email: a.email, password: DEMO_PASSWORD })}>
              <span className="font-semibold">{a.label}</span>
              <span className="text-xs text-slate-500">{a.who}</span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-500">All demo accounts use the password {DEMO_PASSWORD}.</p>
      </div>
    </AuthShell>
  );
}
