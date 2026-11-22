/** Small dependency-free charts (CSS bars and inline SVG), coloured through the theme tokens. */

import type { TrendPoint } from "../api/types";
import { StarIcon } from "./icons";

export function BarList({ items, max, colour = "bg-brand", suffix = "" }: {
  items: { label: string; value: number; hint?: string; colour?: string }[];
  max?: number;
  colour?: string;
  suffix?: string;
}) {
  const top = max ?? Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.label}>
          <div className="mb-1 flex justify-between gap-3 text-[13px]">
            <span className="truncate text-fg">{item.label}</span>
            <span className="font-mono text-[12px] text-muted tabular-nums">
              {item.value}
              {suffix}
              {item.hint && <span className="ml-2">{item.hint}</span>}
            </span>
          </div>
          <div className="h-1.5 bg-sunken">
            <div className={`h-full ${item.colour ?? colour}`} style={{ width: `${Math.min(100, (100 * item.value) / top)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function utilisationColour(pct: number): string {
  return pct >= 100 ? "bg-critical-solid" : pct >= 75 ? "bg-warning-solid" : "bg-ok-solid";
}

export function UtilisationBar({ active, max }: { active: number; max: number }) {
  const pct = Math.round((100 * active) / max);
  return (
    <div className="flex items-center gap-2" title={`${pct}% of workload limit`}>
      <div className="h-1.5 w-24 bg-sunken">
        <div className={`h-full ${utilisationColour(pct)}`} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <span className="font-mono text-[12px] text-muted tabular-nums">
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
  const ticks = [...new Set([0, Math.ceil(max / 2), max])];

  return (
    <figure>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="Incidents created and resolved per day">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={width} y1={y(t)} y2={y(t)} className="stroke-line" />
            <text x={pad.left - 6} y={y(t) + 4} textAnchor="end" className="fill-faint font-mono text-[10px]">{t}</text>
          </g>
        ))}
        {points.map((p, i) => {
          const x = pad.left + i * slot + slot / 2;
          return (
            <g key={p.day}>
              <title>{`${p.day}: ${p.created} created, ${p.resolved} resolved`}</title>
              <rect x={x - bar} y={y(p.created)} width={bar - 1} height={y(0) - y(p.created)} className="fill-brand" />
              <rect x={x} y={y(p.resolved)} width={bar - 1} height={y(0) - y(p.resolved)} className="fill-line-strong" />
              {(i % 2 === 0 || points.length <= 7) && (
                <text x={x} y={height - 6} textAnchor="middle" className="fill-faint font-mono text-[10px]">
                  {p.day.slice(5)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <figcaption className="mt-2 flex gap-4 text-[12px] text-muted">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-brand" />Created</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-line-strong" />Resolved</span>
      </figcaption>
    </figure>
  );
}

export function Stars({ rating, size = 13 }: { rating: number; size?: number }) {
  return (
    <span className="inline-flex items-center gap-px align-[-2px]" aria-label={`${rating} out of 5`} role="img">
      {[1, 2, 3, 4, 5].map((n) => (
        <StarIcon key={n} size={size} filled={n <= rating} className={n <= rating ? "text-warning-solid" : "text-line-strong"} />
      ))}
    </span>
  );
}
