import { NavLink, Outlet } from "react-router";
import type { Role } from "../api/types";
import { useAuth, useUser } from "../auth/AuthContext";
import { LiveEventsProvider, useLiveEvents } from "../hooks/LiveEvents";
import { RoleBadge } from "./badges";
import { NotificationBell } from "./NotificationBell";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
}

// Each role gets its own navigation: the spec asks for a distinct GUI per user type.
const NAV: Record<Role, NavItem[]> = {
  EMPLOYEE: [
    { to: "/employee", label: "My incidents", end: true },
    { to: "/employee/report", label: "Report an incident" },
    { to: "/incidents", label: "Search" },
    { to: "/notifications", label: "Notifications" },
  ],
  TECHNICIAN: [
    { to: "/tech", label: "My queue", end: true },
    { to: "/incidents", label: "All incidents" },
    { to: "/tech/workload", label: "Team workload" },
    { to: "/tech/services", label: "Service health" },
    { to: "/notifications", label: "Notifications" },
  ],
  ADMINISTRATOR: [
    { to: "/admin", label: "Dashboard", end: true },
    { to: "/incidents", label: "Incidents" },
    { to: "/admin/sla", label: "SLA" },
    { to: "/admin/workload", label: "Workload" },
    { to: "/admin/services", label: "Services" },
    { to: "/admin/users", label: "Users" },
    { to: "/admin/config", label: "Configuration" },
    { to: "/admin/audit", label: "Audit log" },
  ],
};

const PORTAL_NAME: Record<Role, string> = {
  EMPLOYEE: "Self-service portal",
  TECHNICIAN: "Support workspace",
  ADMINISTRATOR: "IT operations console",
};

function LiveDot() {
  const { connected } = useLiveEvents();
  return (
    <span className="hidden items-center gap-1.5 text-xs text-slate-500 md:flex" title={connected ? "Live updates connected" : "Reconnecting…"}>
      <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-slate-300"}`} />
      {connected ? "Live" : "Offline"}
    </span>
  );
}

export function Layout() {
  const user = useUser();
  const { logout } = useAuth();

  return (
    <LiveEventsProvider userId={user.id}>
      <div data-role={user.role} className="min-h-screen">
        <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5 sm:px-6">
            <div className="flex items-center gap-2.5">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--accent)] font-bold text-white">IT</span>
              <div className="leading-tight">
                <div className="text-sm font-semibold text-slate-900">I-ITSM</div>
                <div className="text-[11px] text-slate-500">{PORTAL_NAME[user.role]}</div>
              </div>
            </div>
            {/* On small screens the nav gets its own full-width row below the brand and user controls. */}
            <nav className="order-last flex w-full gap-1 overflow-x-auto md:order-none md:w-auto md:flex-1" aria-label="Main">
              {NAV[user.role].map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `rounded-lg px-3 py-1.5 text-sm font-medium whitespace-nowrap ${
                      isActive ? "bg-[var(--accent-soft)] text-[var(--accent-strong)]" : "text-slate-600 hover:bg-slate-100"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
            <div className="ml-auto flex items-center gap-3">
              <LiveDot />
              <NotificationBell />
              <div className="hidden text-right leading-tight sm:block">
                <div className="text-sm font-medium text-slate-800">{user.full_name}</div>
                <RoleBadge role={user.role} />
              </div>
              <button className="btn-ghost btn-sm" onClick={logout}>
                Sign out
              </button>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>
    </LiveEventsProvider>
  );
}
