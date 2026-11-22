import { useState } from "react";
import { Link } from "react-router";
import { incidentsApi } from "../../api/endpoints";
import type { IncidentSummary } from "../../api/types";
import { useUser } from "../../auth/AuthContext";
import { PriorityBadge, StatusBadge } from "../../components/badges";
import { IncidentTable } from "../../components/IncidentTable";
import { Card, ErrorMessage, PageHeader, Pagination, Spinner, Tabs } from "../../components/ui";
import { PlusIcon } from "../../components/icons";
import { useAsync } from "../../hooks/useAsync";
import { useLiveRefresh } from "../../hooks/LiveEvents";
import { OPEN_STATUSES, relativeTime } from "../../lib/format";

type Tab = "open" | "done";

function AttentionList({ items }: { items: IncidentSummary[] }) {
  if (items.length === 0) return null;
  return (
    <section className="mb-6 overflow-hidden rounded-md border border-line border-l-[3px] border-l-warning-solid bg-surface"
             aria-labelledby="attention-heading">
      <header className="flex items-baseline justify-between gap-3 border-b border-line bg-warning-soft px-4 py-2.5">
        <h2 id="attention-heading" className="text-[13.5px]">Needs your attention</h2>
        <span className="text-[12px] text-muted">{items.length} waiting on you</span>
      </header>
      <ul className="divide-y divide-line">
        {items.map((i) => (
          <li key={i.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="mono text-faint">{i.number}</span>
                <PriorityBadge priority={i.priority} />
                <StatusBadge status={i.status} />
              </div>
              <Link to={`/incidents/${i.id}`} className="mt-0.5 block font-medium text-fg hover:text-brand">{i.title}</Link>
            </div>
            <Link to={`/incidents/${i.id}`} className="btn-primary btn-sm">
              {i.status === "PENDING_INFO" ? "Answer the technician" : "Confirm the fix"}
            </Link>
          </li>
        ))}
      </ul>
    </section>
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
        actions={<Link className="btn-primary" to="/employee/report"><PlusIcon size={14} />Report an incident</Link>}
      />
      {attention.data && <AttentionList items={attention.data.items} />}
      <Card flush>
        <Tabs
          className="px-4"
          tabs={[{ key: "open", label: "Open" }, { key: "done", label: "Resolved & closed" }]}
          active={tab}
          onChange={(t) => {
            setTab(t);
            setPage(1);
          }}
        />
        {list.error && <div className="p-4"><ErrorMessage error={list.error} onRetry={list.reload} /></div>}
        {list.loading && !list.data && <div className="px-4"><Spinner /></div>}
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
          <p className="border-t border-line px-4 py-2 text-[12px] text-faint">Last update {relativeTime(list.data.items[0].updated_at)}</p>
        )}
      </Card>
    </>
  );
}
