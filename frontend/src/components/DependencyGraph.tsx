import { useMemo } from "react";
import type { CorrelationReport, ServiceNode } from "../api/types";

const HEALTH_FILL: Record<ServiceNode["health"], string> = {
  HEALTHY: "fill-surface stroke-line-strong",
  DEGRADED: "fill-warning-soft stroke-warning-solid",
  HOTSPOT: "fill-critical-soft stroke-critical-solid",
};

/** Layer = longest path to a service with no dependencies, so infrastructure sits at the bottom. */
function layers(nodes: ServiceNode[]): Map<number, number> {
  const byId = new Map(nodes.map((n) => [n.service_id, n]));
  const depth = new Map<number, number>();
  const visit = (id: number, seen: Set<number>): number => {
    if (depth.has(id)) return depth.get(id)!;
    if (seen.has(id)) return 0; // defensive: the backend keeps the graph acyclic
    seen.add(id);
    const deps = byId.get(id)?.depends_on.filter((d) => byId.has(d)) ?? [];
    const value = deps.length ? 1 + Math.max(...deps.map((d) => visit(d, seen))) : 0;
    depth.set(id, value);
    return value;
  };
  nodes.forEach((n) => visit(n.service_id, new Set()));
  return depth;
}

export function DependencyGraph({ report, onSelect }: { report: CorrelationReport; onSelect?: (serviceId: number) => void }) {
  const layout = useMemo(() => {
    const depth = layers(report.nodes);
    const maxDepth = Math.max(0, ...depth.values());
    const rows: ServiceNode[][] = Array.from({ length: maxDepth + 1 }, () => []);
    report.nodes.forEach((n) => rows[maxDepth - (depth.get(n.service_id) ?? 0)].push(n));
    const width = 760;
    const rowHeight = 92;
    const position = new Map<number, { x: number; y: number }>();
    rows.forEach((row, r) =>
      row.forEach((n, i) => position.set(n.service_id, { x: ((i + 0.5) * width) / row.length, y: 46 + r * rowHeight })),
    );
    return { width, height: rows.length * rowHeight + 10, position };
  }, [report]);

  const nodeW = 156;
  const nodeH = 48;
  return (
    <svg viewBox={`0 0 ${layout.width} ${layout.height}`} className="w-full" role="img" aria-label="Service dependency graph">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" className="fill-faint" />
        </marker>
      </defs>
      {report.edges.map(([from, to]) => {
        const a = layout.position.get(from);
        const b = layout.position.get(to);
        if (!a || !b) return null;
        return (
          <line key={`${from}-${to}`} x1={a.x} y1={a.y + nodeH / 2} x2={b.x} y2={b.y - nodeH / 2 - 2}
                className="stroke-line-strong" strokeWidth={1.5} markerEnd="url(#arrow)" />
        );
      })}
      {report.nodes.map((n) => {
        const p = layout.position.get(n.service_id)!;
        return (
          <g key={n.service_id} transform={`translate(${p.x - nodeW / 2}, ${p.y - nodeH / 2})`}
             className={onSelect ? "cursor-pointer" : ""} onClick={() => onSelect?.(n.service_id)}>
            <title>{`${n.name}: ${n.open_incidents} open, ${n.recent_incidents} in the last 2 h (${n.health.toLowerCase()})`}</title>
            <rect width={nodeW} height={nodeH} rx={4} strokeWidth={n.health === "HOTSPOT" ? 2.5 : 1.5} className={HEALTH_FILL[n.health]} />
            <text x={nodeW / 2} y={20} textAnchor="middle" className="fill-fg text-[11.5px] font-semibold">{n.name}</text>
            <text x={nodeW / 2} y={36} textAnchor="middle" className="fill-muted font-mono text-[10px]">
              {n.open_incidents} open · crit {n.criticality}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
