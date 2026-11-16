import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { authApi } from "../../api/endpoints";
import { useAuth } from "../../auth/AuthContext";
import { errorMessage, useToast } from "../../components/Toasts";
import { AuthShell } from "./Login";

export function RegisterPage() {
  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "", department: "", phone: "" });
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (form.password !== form.confirm) {
      setError("Passwords do not match");
      return;
    }
    setBusy(true);
    setError(undefined);
    try {
      await authApi.register({
        email: form.email,
        full_name: form.full_name,
        password: form.password,
        department: form.department || undefined,
        phone: form.phone || undefined,
      });
      await login(form.email, form.password);
      toast.success("Welcome! Your account is ready.");
      navigate("/employee", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Create your account">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="name">Full name</label>
          <input id="name" className="input" required minLength={2} maxLength={120} value={form.full_name} onChange={set("full_name")} />
        </div>
        <div>
          <label className="label" htmlFor="email">Work email</label>
          <input id="email" className="input" type="email" required value={form.email} onChange={set("email")} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="dept">Department</label>
            <input id="dept" className="input" maxLength={80} value={form.department} onChange={set("department")} />
          </div>
          <div>
            <label className="label" htmlFor="phone">Mobile (for SMS alerts)</label>
            <input id="phone" className="input" placeholder="+91 98…" value={form.phone} onChange={set("phone")} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="pw">Password</label>
            <input id="pw" className="input" type="password" required minLength={8} autoComplete="new-password"
                   value={form.password} onChange={set("password")} />
          </div>
          <div>
            <label className="label" htmlFor="pw2">Confirm</label>
            <input id="pw2" className="input" type="password" required autoComplete="new-password"
                   value={form.confirm} onChange={set("confirm")} />
          </div>
        </div>
        <p className="hint">At least 8 characters with a letter and a digit.</p>
        {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button>
      </form>
      <p className="mt-4 text-sm text-slate-600">
        Already registered? <Link className="link" to="/login">Sign in</Link>
      </p>
    </AuthShell>
  );
}
