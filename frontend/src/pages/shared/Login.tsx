import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { HOME_BY_ROLE, useAuth } from "../../auth/AuthContext";
import { ChevronRightIcon, LogoMark } from "../../components/icons";
import { ThemeToggle } from "../../components/ThemeToggle";
import { errorMessage } from "../../components/Toasts";
import { ErrorMessage } from "../../components/ui";

const DEMO_ACCOUNTS = [
  { email: "adi@decerno.demo", label: "Employee", who: "Adi Rajauria · Finance" },
  { email: "shrey@decerno.demo", label: "Technician", who: "Shrey Bhasker · Infra team lead" },
  { email: "abhinandan@decerno.demo", label: "Administrator", who: "Abhinandan Chandak · System Admin" },
];
const DEMO_PASSWORD = "Demo@1234";

export function AuthShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen bg-canvas lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="hidden flex-col border-r border-line bg-ink p-10 text-on-ink lg:flex xl:p-14">
        <div className="flex items-center gap-3">
          <LogoMark size={40} />
          <span className="text-[24px] font-bold tracking-tight">Decerno</span>
        </div>

        <div className="flex flex-1 flex-col justify-center py-12">
          <div className="max-w-md">
            <p className="font-mono text-[11px] tracking-[0.16em] text-on-ink-muted uppercase">
              Intelligent IT Service Management
            </p>
            <p className="mt-4 text-[34px] leading-[1.15] font-semibold tracking-tight text-balance">
              Every incident, decided and resolved.
            </p>
            <p className="mt-5 text-[15px] leading-relaxed text-on-ink/80 text-pretty">
              Report IT problems, route them to the right technician, and keep every deadline in view.
            </p>
            <div className="mt-10 border-l-2 border-white/20 pl-4">
              <p className="text-[14px]">
                <span className="font-semibold italic">dēcernō</span>
                <span className="text-on-ink-muted"> · Latin, verb</span>
              </p>
              <p className="mt-1 text-[13px] text-on-ink-muted">to decide, to settle, to resolve</p>
            </div>
          </div>
        </div>

        <p className="text-[12px] text-on-ink-muted">CS F213 · Object-Oriented Programming</p>
      </aside>
      <main className="flex items-start justify-center px-5 py-10 sm:items-center sm:py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-3">
              <LogoMark size={34} />
              <span className="text-[21px] font-bold tracking-tight">Decerno</span>
            </div>
            <p className="mt-2 text-[13px] text-muted">Every incident, decided and resolved.</p>
          </div>
          <h1 className="mb-6">{title}</h1>
          {children}
          <div className="mt-10 flex justify-end">
            <ThemeToggle />
          </div>
        </div>
      </main>
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
        {error && <ErrorMessage error={error} />}
        <button className="btn-primary h-9 w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <p className="mt-4 text-[13px] text-muted">
        New employee? <Link className="link" to="/register">Create an account</Link>
      </p>

      <section className="panel mt-8" aria-labelledby="demo-heading">
        <header className="flex items-baseline justify-between gap-3 border-b border-line px-4 py-2.5">
          <h2 id="demo-heading" className="text-[13px]">Demo accounts</h2>
          <span className="text-[12px] text-muted">password <span className="mono text-fg">{DEMO_PASSWORD}</span></span>
        </header>
        <ul className="divide-y divide-line">
          {DEMO_ACCOUNTS.map((a) => (
            <li key={a.email}>
              <button className="group flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-sunken disabled:opacity-50"
                      disabled={busy} onClick={(e) => submit(e, { email: a.email, password: DEMO_PASSWORD })}>
                <span className="min-w-0">
                  <span className="block text-[13.5px] font-medium text-fg">{a.label}</span>
                  <span className="block truncate text-[12px] text-muted">{a.who}</span>
                </span>
                <ChevronRightIcon className="shrink-0 text-faint group-hover:text-brand" />
              </button>
            </li>
          ))}
        </ul>
      </section>
    </AuthShell>
  );
}
