import { useState } from "react";
import { Link } from "react-router";
import { incidentsApi } from "../../api/endpoints";
import type { IncidentSummary } from "../../api/types";
import { useUser } from "../../auth/AuthContext";
import { PriorityBadge, StatusBadge } from "../../components/badges";
import { IncidentTable } from "../../components/IncidentTable";
import { Card, ErrorMessage, PageHeader, Pagination, Spinner, Tabs } from "../../components/ui";
import { useAsync } from "../../hooks/useAsync";
import { useLiveRefresh } from "../../hooks/LiveEvents";
import { OPEN_STATUSES, relativeTime } from "../../lib/format";

type Tab = "open" | "done";

function AttentionList({ items }: { items: IncidentSummary[] }) {
  if (items.length === 0) return null;
  return (
    <Card title="Needs your attention" className="mb-6 border-amber-200">
      <ul className="divide-y divide-slate-100">
        {items.map((i) => (
          <li key={i.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-slate-500">{i.number}</span>
                <PriorityBadge priority={i.priority} />
                <StatusBadge status={i.status} />
              </div>
              <p className="font-medium text-slate-900">{i.title}</p>
            </div>
            <Link to={`/incidents/${i.id}`} className="btn-primary btn-sm">
              {i.status === "PENDING_INFO" ? "Answer the technician" : "Confirm the fix"}
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function MyIncidentsPage() {
  const user = useUser();
  const [tab, setTab] = useState<Tab>("open");
  const [page, setPage] = useState(1);
  const statuses = tab === "open" ? OPEN_STATUSES : ["RESOLVED", "VERIFIED", "CLOSED"];
  const list = useAsync(
    () => incidentsApi.search({ status: statuses, page, page_size: 15, sort: "-updated_at" }),
    [tab, page],
  );
  const attention = useAsync(
    () => incidentsApi.search({ status: ["PENDING_INFO", "RESOLVED"], page_size: 20, sort: "-updated_at" }),
    [],
  );
  useLiveRefresh(() => {
    list.reload();
    attention.reload();
  });

  return (
    <>
      <PageHeader
        title={`Hello, ${user.full_name.split(" ")[0]}`}
        subtitle="Track the incidents you reported and respond when IT needs something from you."
        actions={<Link className="btn-primary" to="/employee/report">+ Report an incident</Link>}
      />
      {attention.data && <AttentionList items={attention.data.items} />}
      <Card>
        <Tabs
          tabs={[{ key: "open", label: "Open" }, { key: "done", label: "Resolved & closed" }]}
          active={tab}
          onChange={(t) => {
            setTab(t);
            setPage(1);
          }}
        />
        {list.error && <ErrorMessage error={list.error} onRetry={list.reload} />}
        {list.loading && !list.data && <Spinner />}
        {list.data && (
          <>
            <IncidentTable incidents={list.data.items} columns={["service", "technician"]}
                           empty={tab === "open" ? "You have no open incidents" : "Nothing resolved yet"} />
            {list.data.total > 0 && (
              <Pagination page={list.data.page} pages={list.data.pages} total={list.data.total} onPage={setPage} />
            )}
          </>
        )}
        {list.data && list.data.items[0] && (
          <p className="text-xs text-slate-400">Last update {relativeTime(list.data.items[0].updated_at)}</p>
        )}
      </Card>
    </>
  );
}
