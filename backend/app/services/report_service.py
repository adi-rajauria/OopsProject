"""Dashboards: overview, technician workload, service analysis, SLA violations, trends.

Computed in Python from the repositories - simple and storage-agnostic at demo scale;
docs/REPORT.md (scalability) explains moving these to SQL aggregates/materialised views.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from statistics import mean

from app.domain.clock import Clock
from app.domain.enums import IncidentStatus, Permission, Priority, SLAStatus, SLATarget
from app.domain.exceptions import UnauthorizedOperationError
from app.domain.incident import Incident
from app.domain.repositories import UnitOfWork
from app.domain.users import User


@dataclass(frozen=True)
class Overview:
    total: int
    open: int
    critical_open: int
    unassigned: int
    resolved: int
    closed: int
    sla_violations: int
    breached_open: int
    at_risk: int
    mttr_hours: float | None
    avg_rating: float | None
    feedback_count: int
    by_status: dict[str, int]
    by_priority_open: dict[str, int]


@dataclass(frozen=True)
class TechnicianStats:
    technician_id: int
    name: str
    code: str
    team: str
    is_available: bool
    is_team_lead: bool
    active: int
    max_workload: int
    utilisation_pct: int
    resolved_total: int
    avg_resolution_hours: float | None
    avg_rating: float | None


@dataclass(frozen=True)
class ServiceStats:
    service_id: int
    code: str
    name: str
    criticality: int
    total: int
    open: int
    violations: int
    mttr_hours: float | None


@dataclass(frozen=True)
class ViolationRow:
    incident_id: int
    number: str
    title: str
    priority: str | None
    status: str
    service: str
    technician: str | None
    target: SLATarget
    due_at: str
    detected_at: str
    overdue_minutes: int


@dataclass(frozen=True)
class ComplianceRow:
    priority: str
    evaluated: int
    met: int
    compliance_pct: float | None


@dataclass(frozen=True)
class TrendPoint:
    day: str
    created: int
    resolved: int


@dataclass(frozen=True)
class SLAReport:
    violations: list[ViolationRow]
    compliance: list[ComplianceRow] = field(default_factory=list)


def _hours(incidents: Iterable[Incident]) -> float | None:
    durations = [(i.resolved_at - i.created_at).total_seconds() / 3600 for i in incidents if i.resolved_at]
    return round(mean(durations), 2) if durations else None


class ReportService:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    @staticmethod
    def _require(viewer: User, *any_of: Permission) -> None:
        if not any(viewer.has_permission(p) for p in any_of):
            raise UnauthorizedOperationError("You are not allowed to view this report")

    def overview(self, viewer: User) -> Overview:
        self._require(viewer, Permission.VIEW_REPORTS)
        now = self._clock.now()
        incidents = self._uow.incidents.list_all()
        open_ = [i for i in incidents if i.status.is_open]
        feedback = self._uow.feedback.list()
        statuses = [i.sla_status(now) for i in open_]
        return Overview(
            total=len(incidents),
            open=len(open_),
            critical_open=sum(i.priority is Priority.P1 for i in open_),
            unassigned=sum(i.assigned_technician_id is None for i in open_),
            resolved=sum(not i.status.is_open for i in incidents),
            closed=sum(i.status is IncidentStatus.CLOSED for i in incidents),
            sla_violations=len(self._uow.sla_violations.list(limit=100_000)),
            breached_open=statuses.count(SLAStatus.BREACHED),
            at_risk=statuses.count(SLAStatus.AT_RISK),
            mttr_hours=_hours(incidents),
            avg_rating=round(mean(f.rating for f in feedback), 2) if feedback else None,
            feedback_count=len(feedback),
            by_status={s.value: c for s, c in Counter(i.status for i in incidents).items()},
            by_priority_open={p.value: sum(i.priority is p for i in open_) for p in Priority},
        )

    def technician_workload(self, viewer: User) -> list[TechnicianStats]:
        self._require(viewer, Permission.VIEW_REPORTS, Permission.WORK_INCIDENTS)
        incidents = self._uow.incidents.list_all()
        counts = self._uow.incidents.active_counts_by_technician()
        ratings = {f.incident_id: f.rating for f in self._uow.feedback.list()}
        by_tech: dict[int, list[Incident]] = defaultdict(list)
        for i in incidents:
            if i.assigned_technician_id is not None and i.resolved_at is not None:
                by_tech[i.assigned_technician_id].append(i)
        rows = []
        for t in self._uow.users.list_technicians():
            resolved = by_tech[t.id]
            tech_ratings = [ratings[i.id] for i in resolved if i.id in ratings]
            active = counts.get(t.id, 0)
            rows.append(
                TechnicianStats(
                    t.id,
                    t.full_name,
                    t.display_code,
                    t.profile.team,
                    t.profile.is_available and t.is_active,
                    t.profile.is_team_lead,
                    active,
                    t.profile.max_workload,
                    round(100 * active / t.profile.max_workload),
                    len(resolved),
                    _hours(resolved),
                    round(mean(tech_ratings), 2) if tech_ratings else None,
                )
            )
        return sorted(rows, key=lambda r: (-r.active, r.name))

    def service_analysis(self, viewer: User) -> list[ServiceStats]:
        self._require(viewer, Permission.VIEW_REPORTS)
        incidents = self._uow.incidents.list_all()
        service_of = {i.id: i.service_id for i in incidents}
        violations = Counter(service_of.get(v.incident_id) for v in self._uow.sla_violations.list(limit=100_000))
        by_service: dict[int, list[Incident]] = defaultdict(list)
        for i in incidents:
            by_service[i.service_id].append(i)
        rows = [
            ServiceStats(
                s.id,
                s.code,
                s.name,
                s.business_criticality,
                len(by_service[s.id]),
                sum(i.status.is_open for i in by_service[s.id]),
                violations[s.id],
                _hours(by_service[s.id]),
            )
            for s in self._uow.services.list()
        ]
        return sorted(rows, key=lambda r: (-r.total, r.name))

    def sla_report(self, viewer: User) -> SLAReport:
        self._require(viewer, Permission.VIEW_REPORTS)
        incidents = {i.id: i for i in self._uow.incidents.list_all()}
        services = {s.id: s.name for s in self._uow.services.list()}
        users = {u.id: u.full_name for u in self._uow.users.list()}
        rows = []
        for v in self._uow.sla_violations.list(limit=1000):
            i = incidents.get(v.incident_id)
            if i is None:
                continue
            rows.append(
                ViolationRow(
                    i.id,
                    i.number,
                    i.title,
                    i.priority.value if i.priority else None,
                    i.status.value,
                    services.get(i.service_id, "?"),
                    users.get(i.assigned_technician_id),
                    v.target,
                    v.due_at.isoformat(),
                    v.detected_at.isoformat(),
                    v.overdue_minutes,
                )
            )
        return SLAReport(rows, self._compliance(incidents.values()))

    @staticmethod
    def _compliance(incidents: Iterable[Incident]) -> list[ComplianceRow]:
        """Resolution compliance per priority over incidents whose resolution target is settled."""
        rows = []
        for p in Priority:
            settled = [
                i
                for i in incidents
                if i.priority is p
                and i.sla is not None
                and (i.resolved_at is not None or i.sla.is_breached(SLATarget.RESOLUTION))
            ]
            met = sum(not i.sla.is_breached(SLATarget.RESOLUTION) for i in settled)
            rows.append(
                ComplianceRow(p.value, len(settled), met, round(100 * met / len(settled), 1) if settled else None)
            )
        return rows

    def trends(self, viewer: User, days: int = 14) -> list[TrendPoint]:
        self._require(viewer, Permission.VIEW_REPORTS)
        days = min(max(days, 1), 90)
        today = self._clock.now().date()
        created = Counter(i.created_at.date() for i in self._uow.incidents.list_all())
        resolved = Counter(i.resolved_at.date() for i in self._uow.incidents.list_all() if i.resolved_at)
        span = [today - timedelta(days=n) for n in range(days - 1, -1, -1)]
        return [TrendPoint(d.isoformat(), created[d], resolved[d]) for d in span]
