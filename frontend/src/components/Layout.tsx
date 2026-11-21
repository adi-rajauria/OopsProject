import { useEffect, useState, type ComponentType } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import type { Role, User } from "../api/types";
import { useAuth, useUser } from "../auth/AuthContext";
import { LiveEventsProvider, useLiveEvents } from "../hooks/LiveEvents";
import { RoleBadge } from "./badges";
import {
  BarsIcon, BellIcon, CloseIcon, FileIcon, GaugeIcon, GridIcon, InboxIcon, ListIcon, LogoMark, LogOutIcon, MenuIcon,
  NetworkIcon, PlusIcon, SearchIcon, SlidersIcon, UsersIcon,
} from "./icons";
import { NotificationBell } from "./NotificationBell";
import { ThemeToggle } from "./ThemeToggle";

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ size?: number }>;
  end?: boolean;
}
interface NavGroup {
  label?: string;
  items: NavItem[];
}

// Each role gets its own navigation and shell: the spec asks for a distinct GUI per user type.
const NAV: Record<Role, NavGroup[]> = {
  EMPLOYEE: [{
    items: [
      { to: "/employee", label: "My incidents", icon: InboxIcon, end: true },
      { to: "/employee/report", label: "Report an incident", icon: PlusIcon },
      { to: "/incidents", label: "Search", icon: SearchIcon },
      { to: "/notifications", label: "Notifications", icon: BellIcon },
    ],
  }],
  TECHNICIAN: [
    {
      label: "Work",
      items: [
        { to: "/tech", label: "My queue", icon: InboxIcon, end: true },
        { to: "/incidents", label: "All incidents", icon: ListIcon },
        { to: "/notifications", label: "Notifications", icon: BellIcon },
      ],
    },
    {
      label: "Team",
      items: [
        { to: "/tech/workload", label: "Team workload", icon: BarsIcon },
        { to: "/tech/services", label: "Service health", icon: NetworkIcon },
      ],
    },
  ],
  ADMINISTRATOR: [
    {
      label: "Operations",
      items: [
        { to: "/admin", label: "Dashboard", icon: GridIcon, end: true },
        { to: "/incidents", label: "Incidents", icon: ListIcon },
        { to: "/admin/sla", label: "SLA", icon: GaugeIcon },
      ],
    },
    {
      label: "Reports",
      items: [
        { to: "/admin/workload", label: "Workload", icon: BarsIcon },
        { to: "/admin/services", label: "Services", icon: NetworkIcon },
      ],
    },
    {
      label: "Administration",
      items: [
        { to: "/admin/users", label: "Users", icon: UsersIcon },
        { to: "/admin/config", label: "Configuration", icon: SlidersIcon },
        { to: "/admin/audit", label: "Audit log", icon: FileIcon },
      ],
    },
  ],
};

const PORTAL_NAME: Record<Role, string> = {
  EMPLOYEE: "Self-service",
  TECHNICIAN: "Support desk",
  ADMINISTRATOR: "Operations console",
};

function LiveDot() {
  const { connected } = useLiveEvents();
  return (
    <span className="flex items-center gap-1.5 text-[12px] text-muted" title={connected ? "Live updates connected" : "Reconnecting…"}>
      <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-ok-solid" : "bg-faint"}`} />
      <span className="hidden sm:inline">{connected ? "Live" : "Reconnecting"}</span>
    </span>
  );
}

function Wordmark({ role }: { role: Role }) {
  return (
    <Link to="/" className="flex items-center gap-2.5" aria-label="I-ITSM home">
      <LogoMark size={26} />
      <span className="leading-tight">
        <span className="block text-[14px] font-semibold tracking-tight text-fg">I-ITSM</span>
        <span className="block text-[11.5px] text-muted">{PORTAL_NAME[role]}</span>
      </span>
    </Link>
  );
}

// ---------------------------------------------------------------- staff: sidebar console

function SidebarNav({ groups }: { groups: NavGroup[] }) {
  return (
    <nav aria-label="Main" className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
      {groups.map((group, index) => (
        <div key={group.label ?? index}>
          {group.label && <div className="mb-1 px-2 text-[11.5px] font-medium text-faint">{group.label}</div>}
          <ul className="space-y-px">
            {group.items.map(({ to, label, icon: Icon, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `relative flex h-8 items-center gap-2.5 rounded px-2 text-[13.5px] transition-colors ${
                      isActive
                        ? "bg-surface font-medium text-fg shadow-[inset_2px_0_0_var(--c-brand)]"
                        : "text-muted hover:bg-surface/70 hover:text-fg"
                    }`
                  }
                >
                  <Icon size={15} />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function SidebarFooter({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <div className="space-y-3 border-t border-line px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0 leading-tight">
          <div className="truncate text-[13px] font-medium text-fg">{user.full_name}</div>
          <div className="mt-1"><RoleBadge role={user.role} /></div>
        </div>
        <button className="btn-ghost btn-sm" onClick={onLogout} title="Sign out">
          <LogOutIcon size={14} />
          Sign out
        </button>
      </div>
      <ThemeToggle />
    </div>
  );
}

function StaffShell({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [drawer, setDrawer] = useState(false);
  const location = useLocation();
  useEffect(() => setDrawer(false), [location.pathname]);
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawer(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawer]);

  const sidebar = (
    <>
      <div className="flex h-14 items-center justify-between border-b border-line px-4">
        <Wordmark role={user.role} />
        <button className="btn-ghost btn-sm lg:hidden" onClick={() => setDrawer(false)} aria-label="Close menu">
          <CloseIcon />
        </button>
      </div>
      <SidebarNav groups={NAV[user.role]} />
      <SidebarFooter user={user} onLogout={onLogout} />
    </>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[232px_minmax(0,1fr)] lg:bg-sidebar">
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-line bg-sidebar lg:flex">{sidebar}</aside>

      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <button className="absolute inset-0 bg-black/40" aria-label="Close menu" onClick={() => setDrawer(false)} />
          <aside className="relative flex h-full w-72 max-w-[85vw] flex-col bg-sidebar shadow-pop">{sidebar}</aside>
        </div>
      )}

      <div className="min-h-screen min-w-0 bg-canvas">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-canvas px-4 sm:px-6 lg:px-8">
          <button className="btn-ghost -ml-2 px-2 lg:hidden" onClick={() => setDrawer(true)} aria-label="Open menu" aria-expanded={drawer}>
            <MenuIcon size={18} />
          </button>
          <div className="lg:hidden"><Wordmark role={user.role} /></div>
          <div className="ml-auto flex items-center gap-3">
            <LiveDot />
            <NotificationBell />
          </div>
        </header>
        <main className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- employee: light portal

function EmployeeShell({ user, onLogout }: { user: User; onLogout: () => void }) {
  const items = NAV.EMPLOYEE[0].items;
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1080px] flex-wrap items-center gap-x-8 px-4 sm:px-6">
          <div className="flex h-14 items-center">
            <Wordmark role={user.role} />
          </div>
          <nav aria-label="Main" className="order-last -mx-4 flex w-[calc(100%+2rem)] gap-5 overflow-x-auto border-t border-line px-4 sm:-mx-6 sm:w-[calc(100%+3rem)] sm:px-6 md:order-none md:mx-0 md:w-auto md:border-0 md:px-0">
            {items.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `-mb-px flex h-11 items-center border-b-2 text-[13.5px] whitespace-nowrap transition-colors md:h-14 ${
                    isActive ? "border-brand font-medium text-fg" : "border-transparent text-muted hover:text-fg"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex h-14 items-center gap-3">
            <LiveDot />
            <NotificationBell />
            <span className="hidden text-[13px] text-fg lg:inline">{user.full_name}</span>
            <button className="btn-ghost btn-sm" onClick={onLogout} title="Sign out" aria-label="Sign out">
              <LogOutIcon size={14} />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1080px] px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
        <div className="mt-10 flex justify-end border-t border-line pt-4">
          <ThemeToggle />
        </div>
      </main>
    </div>
  );
}

export function Layout() {
  const user = useUser();
  const { logout } = useAuth();
  return (
    <LiveEventsProvider userId={user.id}>
      <div data-role={user.role}>
        {user.role === "EMPLOYEE" ? <EmployeeShell user={user} onLogout={logout} /> : <StaffShell user={user} onLogout={logout} />}
      </div>
    </LiveEventsProvider>
  );
}
