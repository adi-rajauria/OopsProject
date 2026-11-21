import type { ReactNode } from "react";
import { AlertIcon } from "./icons";
import { errorMessage } from "./Toasts";

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-[13px] text-muted" role="status">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-line-strong border-t-brand" />
      {label}
    </div>
  );
}

export function ErrorMessage({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="flex items-start justify-between gap-4 rounded border border-critical/30 bg-critical-soft px-3 py-2.5 text-[13px] text-critical"
         role="alert">
      <span className="flex items-start gap-2">
        <AlertIcon className="mt-0.5 shrink-0" size={14} />
        {errorMessage(error)}
      </span>
      {onRetry && (
        <button className="btn-secondary btn-sm" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

/** Quiet empty state; sits inside a panel, so it draws no box of its own. */
export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="px-4 py-10 text-center">
      <p className="font-medium text-fg">{title}</p>
      {children && <div className="mt-1 text-[13px] text-muted">{children}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions, eyebrow }: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  eyebrow?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-[13px] text-muted">{eyebrow}</div>}
        <h1>{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-[13px] text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** A bordered panel with an optional title row. `flush` drops the body padding (for tables and lists). */
export function Card({ title, actions, children, className = "", flush = false }: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  flush?: boolean;
}) {
  return (
    <section className={`panel min-w-0 ${className}`}>
      {(title || actions) && (
        <header className="flex min-h-10 items-center justify-between gap-3 border-b border-line px-4 py-2">
          {typeof title === "string" ? <h2 className="text-[13.5px]">{title}</h2> : title}
          {actions && <div className="flex items-center gap-3 text-[13px]">{actions}</div>}
        </header>
      )}
      <div className={flush ? "" : "card-body"}>{children}</div>
    </section>
  );
}

/** Unboxed section: a heading on a rule. Used where a card would only add noise. */
export function Section({ title, actions, children, className = "" }: {
  title: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={className}>
      <div className="mb-3 flex items-baseline justify-between gap-3 border-b border-line pb-2">
        {typeof title === "string" ? <h2>{title}</h2> : title}
        {actions && <div className="flex items-center gap-3 text-[13px]">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

const STAT_TONES = {
  default: "text-fg",
  danger: "text-critical",
  warning: "text-warning",
  success: "text-ok",
};
type Tone = keyof typeof STAT_TONES;

/** One figure in a StatStrip. */
export function Stat({ label, value, hint, tone = "default" }: { label: string; value: ReactNode; hint?: ReactNode; tone?: Tone }) {
  return (
    <div className="min-w-0 px-4 py-3">
      <div className="text-[12px] text-muted">{label}</div>
      <div className={`mt-0.5 font-mono text-[22px] leading-tight font-medium tabular-nums ${STAT_TONES[tone]}`}>{value}</div>
      {hint && <div className="mt-0.5 text-[12px] text-muted">{hint}</div>}
    </div>
  );
}

/** A row of figures in one ruled panel instead of a grid of identical cards. */
export function StatStrip({ children, columns = 4 }: { children: ReactNode; columns?: 2 | 3 | 4 | 5 | 6 }) {
  const cols = { 2: "sm:grid-cols-2", 3: "sm:grid-cols-3", 4: "sm:grid-cols-2 lg:grid-cols-4", 5: "sm:grid-cols-3 lg:grid-cols-5", 6: "sm:grid-cols-3 lg:grid-cols-6" }[columns];
  return (
    // 1px gaps over a line-coloured background draw the hairlines between cells.
    <div className={`grid grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line ${cols} [&>*]:bg-surface`}>
      {children}
    </div>
  );
}

/** Kept for pages not yet moved to StatStrip. */
export function StatCard(props: { label: string; value: ReactNode; hint?: ReactNode; tone?: Tone }) {
  return (
    <div className="panel">
      <Stat {...props} />
    </div>
  );
}

export function Field({ label, hint, children, htmlFor }: {
  label: string;
  hint?: ReactNode;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <div>
      <label className="label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {hint && <p className="hint">{hint}</p>}
    </div>
  );
}

export function Pagination({ page, pages, total, onPage }: {
  page: number;
  pages: number;
  total: number;
  onPage: (page: number) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-t border-line px-3 py-2.5 text-[13px] text-muted">
      <span>
        <span className="font-mono tabular-nums text-fg">{total}</span> incident{total === 1 ? "" : "s"}
      </span>
      <div className="flex items-center gap-2">
        <button className="btn-secondary btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <span className="font-mono text-[12px] tabular-nums">
          {page} / {pages}
        </span>
        <button className="btn-secondary btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}

export function Tabs<T extends string>({ tabs, active, onChange, className = "mb-4" }: {
  tabs: { key: T; label: ReactNode }[];
  active: T;
  onChange: (key: T) => void;
  className?: string;
}) {
  return (
    <div className={`flex gap-4 overflow-x-auto border-b border-line ${className}`} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={t.key === active}
          onClick={() => onChange(t.key)}
          className={`-mb-px border-b-2 py-2 text-[13px] font-medium whitespace-nowrap transition-colors ${
            t.key === active ? "border-brand text-fg" : "border-transparent text-muted hover:text-fg"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

/** Callout for a state the user must act on (pending info, awaiting verification…). */
export function Notice({ tone = "warning", title, children, actions }: {
  tone?: "warning" | "ok" | "critical" | "info";
  title?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  const tones = {
    warning: "border-l-warning-solid bg-warning-soft",
    ok: "border-l-ok-solid bg-ok-soft",
    critical: "border-l-critical-solid bg-critical-soft",
    info: "border-l-brand bg-brand-soft",
  };
  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 rounded-r border-l-[3px] px-4 py-3 text-[13px] text-fg ${tones[tone]}`}>
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? "mt-0.5" : ""}>{children}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
