/** Small dependency-free charts (CSS bars and inline SVG). */

import type { TrendPoint } from "../api/types";

export function BarList({ items, max, colour = "bg-[var(--accent)]", suffix = "" }: {
  items: { label: string; value: number; hint?: string; colour?: string }[];
  max?: number;
  colour?: string;
  suffix?: string;
}) {
  const top = max ?? Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="space-y-2.5">
      {items.map((item) => (
        <li key={item.label}>
          <div className="mb-1 flex justify-between gap-3 text-sm">
            <span className="truncate text-slate-700">{item.label}</span>
            <span className="text-slate-500 tabular-nums">
              {item.value}
              {suffix}
              {item.hint && <span className="ml-2 text-xs">{item.hint}</span>}
            </span>
          </div>
          <div className="h-2 rounded-full bg-slate-100">
            <div
              className={`h-full rounded-full ${item.colour ?? colour}`}
              style={{ width: `${Math.min(100, (100 * item.value) / top)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function UtilisationBar({ active, max }: { active: number; max: number }) {
  const pct = Math.round((100 * active) / max);
  const colour = pct >= 100 ? "bg-rose-500" : pct >= 75 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-28 rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${colour}`} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <span className="text-xs text-slate-500 tabular-nums">
        {active}/{max}
      </span>
    </div>
  );
}

/** Grouped bars: incidents created vs resolved per day. */
export function TrendChart({ points }: { points: TrendPoint[] }) {
  const width = 640;
  const height = 180;
  const pad = { left: 28, bottom: 24, top: 8 };
  const max = Math.max(1, ...points.flatMap((p) => [p.created, p.resolved]));
  const slot = (width - pad.left) / Math.max(1, points.length);
  const bar = Math.max(3, slot / 3);
  const y = (v: number) => pad.top + (height - pad.top - pad.bottom) * (1 - v / max);
  const ticks = [0, Math.ceil(max / 2), max];

  return (
    <figure>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="Incidents created and resolved per day">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={width} y1={y(t)} y2={y(t)} className="stroke-slate-100" />
            <text x={pad.left - 6} y={y(t) + 4} textAnchor="end" className="fill-slate-400 text-[10px]">{t}</text>
          </g>
        ))}
        {points.map((p, i) => {
          const x = pad.left + i * slot + slot / 2;
          return (
            <g key={p.day}>
              <title>{`${p.day}: ${p.created} created, ${p.resolved} resolved`}</title>
              <rect x={x - bar} y={y(p.created)} width={bar - 1} height={y(0) - y(p.created)} rx={2} className="fill-[var(--accent)]" />
              <rect x={x} y={y(p.resolved)} width={bar - 1} height={y(0) - y(p.resolved)} rx={2} className="fill-emerald-400" />
              {(i % 2 === 0 || points.length <= 7) && (
                <text x={x} y={height - 6} textAnchor="middle" className="fill-slate-400 text-[10px]">
                  {p.day.slice(5)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <figcaption className="mt-2 flex gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-[var(--accent)]" />Created</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-emerald-400" />Resolved</span>
      </figcaption>
    </figure>
  );
}

export function Stars({ rating }: { rating: number }) {
  return (
    <span className="text-amber-500" aria-label={`${rating} out of 5`}>
      {"★".repeat(rating)}
      <span className="text-slate-300">{"★".repeat(5 - rating)}</span>
    </span>
  );
}
